import os
import shutil
import builder
import patch_verifier
import robostack_AI as ai
import re


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
    recipe = f"./recipes/{package_name}"
    with open(recipe, "r") as recipe_file:
        data = recipe_file.read()
    pattern = r'git_url:\s*(.*)'
    match = re.search(pattern, data)
    if match:
        git_url = match.group(1)
        print(f"Extracted git_url: {git_url}")
    else:
        print("git_url not found in the source.")
    data


    pass


skip_existing_flag = "  - /home/ryan/bld_work"
target_file = "vinca_linux_64.yaml"



recipes_dir = "../recipes"
source_vinca = f"./{target_file}"
target_vinca = f"./vinca.yaml"
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
            replace_patch(patch_location,patch_package_dir)