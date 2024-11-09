import os
import shutil
import builder
import patch_verifier
import robostack_AI as ai
import re
import git
import time
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', type=str, required=True, help="IP Address for Accessing LLM Model API")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Stops any changes from occuring to RoboStack")
    parser.add_argument('-s', '--skip_existing', type=str, default=None, help="The Skip existing directory for packages that won't be checked for failing builds. Used for faster build times")
    return parser.parse_args()

def filter_strings(strings, substring):
    return [s for s in strings if substring not in s]

def extract_file_paths(log_content):
    path_pattern = r'(?:^|\s)(\S+/\S+)'
    matches = re.findall(path_pattern, log_content)
    return matches

def split_and_filter_string(strings, split_string):
    def extract_single_path(path):
        parts = path.split(split_string)
        return parts[-1] if len(parts) > 1 else None

    extracted = [extract_single_path(dir) for dir in strings]
    return [path for path in extracted if path is not None]

def isolate_build_error(package, log_path):
    with open(log_path, 'r') as log:
        log_data = log.read()
        pattern = f'Starting build for {package}'
        modified_log = re.split(pattern, log_data, maxsplit=1)[-1]
        pattern = r'-- Build files have been written to: \$SRC_DIR/build'
        modified_log = re.split(pattern, modified_log, maxsplit=1)[-1]
        pattern = r'ERROR: Build failed!'
        modified_log = re.split(pattern, modified_log, maxsplit=1)[0]
        directories = extract_file_paths(modified_log)
        mod_directories = filter_strings(directories, '$PREFIX')
        mod_directories = filter_strings(mod_directories, 'CMakeFiles')
        mod_directories = filter_strings(mod_directories, '[')
        mod_directories = filter_strings(mod_directories,"conda_build.sh")
        mod_directories = split_and_filter_string(mod_directories,f"{package}/src/work/")
        added_directories = []
        equivelant_name = package.removeprefix("ros-humble-")
        equivelant_name = equivelant_name.replace("-","_")
        for mod_directory in mod_directories:
            new_directory = f'./temp/{equivelant_name}/{mod_directory}'
            full_directory = os.path.abspath(new_directory)
            if os.path.isfile(full_directory):
                added_directories.append(full_directory)
        return modified_log, added_directories

def remove_recipe_patch(package_name):
    recipe_path = f'./recipes/{package_name}/recipe.yaml'
    patch_dir_path = f'./recipes/{package_name}/patch'
    shutil.rmtree(patch_dir_path)

    with open(recipe_path, 'r+') as recipe_file:
        content = recipe_file.read()
        edit = re.sub(r'patches:\s*\n(    - .*\n)*', '', content)
        recipe_file.seek(0)
        recipe_file.write(edit)
        recipe_file.truncate()

def replace_file(content, target):
    os.remove(target)
    with open(target,"w") as target_file:
        target_file.write(content)

def insert_after_category(file_path, category_name, added_insert):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    for i, line in enumerate(lines):
        if category_name in line:
            # Insert the URL on the next line
            lines.insert(i + 1, added_insert + '\n')
            break
        
    with open(file_path, 'w') as file:
        file.writelines(lines)

def fetch_script(package_name, log_path):
    recipe = f"./recipes/{package_name}/recipe.yaml"
    patch_path = f"./recipes/{package_name}/patch/{package_name}.patch"
    local_path = f'./temp/{package_name}'
    temp_path = "./temp"

    with open(recipe, "r") as recipe_file:
        data = recipe_file.read()
    pattern = r'git_url:\s*(.*)'
    match = re.search(pattern, data)

    if match:
        git_url = match.group(1)
        print(f"Extracted git_url: {git_url}")
    else:
        print("git_url not found in the source.")

    pattern = r'git_rev:\s*(.*)'
    match = re.search(pattern, data)
    if match:
        git_rev = match.group(1)
        print(f"Extracted git_rev: {git_rev}")
    else:
        print("git_url not found in the source.")

    if os.path.exists(temp_path):
        print("Cleaning temp file")
        shutil.rmtree(temp_path)

    git_rev = re.sub(r'(.*?\/)(\d+\.\d+\.\d+-\d+)$', r'\1', git_rev)
    git_rev = git_rev.rstrip('/')
    os.mkdir(temp_path)
    equivelant_name = local_path.replace("ros-humble-", "", 1)
    equivelant_name = equivelant_name.replace("-","_")
    repo = git.Repo.clone_from(git_url,equivelant_name,branch=git_rev)
    repo.git.checkout(git_rev)
    try:
        repo.git.execute(['git','apply', '-p2',os.path.abspath(patch_path)])
        print("Patch Successfully Applied")
    except git.exc.GitCommandError:
        print("Patch was corrupted. Solving from scratch.")
        remove_recipe_patch(package_name)
        log_path = builder.build_packages()
        build_success, failed_package = patch_verifier.check(log_path)
        if not build_success:
            return fetch_script(package_name, log_path)
        else:
            return None, None, None
    pass

    filtered_log, potential_paths = isolate_build_error(package_name, log_path)
    return filtered_log, potential_paths, repo




target_file = "vinca_linux_64.yaml"
recipes_dir = "../recipes"
source_vinca = f"./{target_file}"
target_vinca = f"./vinca.yaml"




def run(args):
    skip_existing_flag = f"  - {args.skip_existing}"
    start_1 = time.time()
    shutil.copyfile(source_vinca, target_vinca)
    if not(args.skip_existing is None or args.skip_existing == ""):
        skip_existing_flag = f"  - {args.skip_existing}"
        insert_after_category(target_vinca,"skip_existing:", skip_existing_flag)
    
    start_2 = time.time()
    build_log_path = builder.run_all()
    start_3 = time.time()
    build_success, failed_package = patch_verifier.check(build_log_path)
    start_4 = time.time()
    print(f"Built Successfully: {build_success}")

    if not build_success:
            start_5 = time.time()
            patch_location = f"./recipes/{failed_package}/patch/{failed_package}.patch"
            filtered_log, bad_scripts, repo = fetch_script(failed_package,build_log_path)
            if bad_scripts is None:
                print(f"{failed_package} patch removal resulted in successful build.")
                return
            target_script = bad_scripts[0]
            start_6 = time.time()
            ai.fix(ip=args.ip, bad_script_path=target_script,error_log=filtered_log)
            start_7 = time.time()
            equivelant_name = failed_package.removeprefix("ros-humble-")
            equivelant_name = equivelant_name.replace("-","_")
            patch = repo.git.execute(['git', 'diff', f'--src-prefix=a/{equivelant_name}/', f'--dst-prefix=b/{equivelant_name}/'])
            replace_file(patch,patch_location)
            start_8 = time.time()
            build_log_path_2 = builder.build_packages()
            build_success_2, failed_package_2 = patch_verifier.check(build_log_path_2)
            start_9 = time.time()
            if not build_success_2:
                print("unable to resolve.")
                raise Exception("Unable to patch package")
            else:
                print("Patch Sucessfully resolved Build Error.")
                patch_package_dir = f"./patch/{failed_package}.patch"
                if not args.debug:
                    replace_file(patch,patch_package_dir)
            print(f"Setup : {round(start_2 - start_1)}, Build 1 : {round(start_3-start_2)}, Check 1 : {round(start_4-start_3)}, Script Retrieval : {round(start_6-start_5)}, AI Repair : {round(start_7 - start_6)}")
            print(f"Patch Generation : {round(start_8-start_7)}, Build 2 : {round(start_9-start_8)}")
            return [start_1, start_2, start_3, start_4, start_5, start_6, start_7, start_8, start_9]

if "__main__" == __name__:
    args = parse_arguments()
    run(args)
