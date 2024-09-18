import os
import shutil
import builder
import patch_verifier
import robostack_AI as ai
import subprocess
import re
from github import Github, Auth
import git
import patch

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

def apply_patch(repo_path, patch_file):
    try:
        # Open the repository
        repo = git.Repo(repo_path)
        
        # Read the patch file
        with open(patch_file, 'r') as file:
            patch_content = file.read()
        
        # Apply the patch
        result = repo.git.apply(patch_content)
        
        print("Patch applied successfully.")
        print(result)
    except git.GitCommandError as e:
        print(f"Failed to apply patch: {e}")
    except FileNotFoundError:
        print(f"Patch file not found: {patch_file}")
    except Exception as e:
        print(f"An error occurred: {e}")



def vibe_check(source):
    with open(source, "r") as source_file:
        pass
DEBUG_PATCH = "./DEBUG_HARDWARE_INTERFACE.patch"
vibe_check(DEBUG_PATCH)

def replace_patch(source, target):
    os.remove(target)
    with open(target,"w") as target_file:
        with open(source, "r") as source_file:
            target_file.write(source_file.read())

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

def fetch_script(package_name):
    
    DEBUG_PATCH = "./DEBUG_HARDWARE_INTERFACE.patch"

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
        log_dir = builder.build_packages()
        build_success, failed_package = patch_verifier.check(log_dir)
    pass


skip_existing_flag = "  - /home/ryan/bld_work"
target_file = "vinca_linux_64.yaml"
recipes_dir = "../recipes"
source_vinca = f"./{target_file}"
target_vinca = f"./vinca.yaml"




def run():
    shutil.copyfile(source_vinca, target_vinca)
    insert_after_category(target_vinca,"skip_existing:", skip_existing_flag)
    build_log_path = builder.run_all()
    build_success, failed_package = patch_verifier.check(build_log_path)
    print(f"Built Successfully: {build_success}")

    if not build_success:
            patch_location = f"./recipes/{failed_package}/patch/{failed_package}.patch"
            patch_arg_list = ['-e', build_log_path, '-t', patch_location]
            if os.path.exists(patch_location):
                print("patch Exists")
                patch_arg_list.append('-p')
                patch_arg_list.append(patch_location)


            fetch_script(failed_package)



            ai_parser = ai.get_argparser()
            ai_args = ai_parser.parse_args(patch_arg_list)
            ai.fix(ai_args)
            print(DEBUG_PATCH)


                
            #THIS IS DEBUGGING CODE AND NEEDS TO BE CHANGED
            replace_patch(DEBUG_PATCH, patch_location)

            build_log_path_2 = builder.build_packages()
            build_success_2, failed_package_2 = patch_verifier.check(build_log_path_2)
            
            if not build_success_2:
                print("unable to resolve.")
                raise Exception("Unable to patch package")
            else:
                print("Patch Sucessfully resolved Build Error.")
                patch_package_dir = f"./patch/{failed_package}.patch"
                #replace_patch(patch_location,patch_package_dir)

if "__main__" == __name__:
    failed_package = 'ros-humble-hardware-interface'
    builder.build_recipes()
    fetch_script(failed_package)
    #run()