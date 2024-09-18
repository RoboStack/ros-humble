from github import Github, Auth
import git
import os
from subprocess import Popen
import shutil
import glob
import builder
import patch_verifier
from time import sleep
import robostack_AI as ai

###################SETUP###################

def DEBUG_REPLACE_PATCH(source, target):
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


DEBUG_PATCH = "DEBUG_HARDWARE_INTERFACE.patch"
skip_existing_flag = "  - /home/ryan/bld_work"
target_filename = "vinca_linux_64.yaml"
branches_dir = "branches/"
repo_name = "Striker146/ros-humble-github-actions"
auth_token_file = open("auth_token.txt")
auth_token_str = auth_token_file.read()
local_repo_dir = "ros-humble-github-actions"
is_windows = "nt" == os.name

###################GET GIT PULL REQUEST###################

auth = Auth.Token(auth_token_str)

g = Github(auth=auth)

repo = g.get_repo(repo_name)


pr = list(repo.get_pulls(state='open'))
branch_name = pr[0].head.ref
branch_repo = pr[0].head.repo.full_name

clone_url = f"https://github.com/{branch_repo}.git"

repo_local = git.Repo(local_repo_dir)
repo_local.remotes.origin.fetch()
repo_local.git.checkout(branch_name)
repo_local.remotes.origin.pull(branch_name)

pr_directory = f"{branches_dir}{branch_name}"

if os.path.exists(pr_directory):
    if is_windows:
        pr_directory_correct = pr_directory.replace("/","\\")
        Popen(f"path_remover.bat { pr_directory_correct }")
        sleep(0.5)
    else:
        shutil.rmtree(pr_directory)
pr_repo = git.Repo.clone_from(clone_url, pr_directory, branch=branch_name)


files_changed = pr[0].get_files()

###################BUILD###################

target_file = next(filter(lambda f: f.filename == target_filename, files_changed), None)

if target_file:
    source_vinca = f"{pr_directory}/{target_file.filename}"
    target_vinca = f"{local_repo_dir}/vinca.yaml"
    recipes_dir = f"{local_repo_dir}/recipes"
    if os.path.isfile(target_vinca):
        os.remove(target_vinca)
    shutil.copyfile(source_vinca, target_vinca)
    insert_after_category(target_vinca,"skip_existing:", skip_existing_flag)

    arg_list = ['-s', local_repo_dir]
    builder_parser = builder.get_argparser()
    builder_args =  builder_parser.parse_args(arg_list)
    build_log_path = builder.run_all(builder_args)
    build_success, failed_package = patch_verifier.check(build_log_path)
    print(f"Built Successfully: {build_success}")

    if not build_success:
        patch_location = f"{local_repo_dir}/recipes/{failed_package}/patch/{failed_package}.patch"
        patch_arg_list = ['-e', build_log_path, '-t', patch_location]
        if os.path.exists(patch_location):
            print("patch Exists")
            patch_arg_list.append('-p')
            patch_arg_list.append(patch_location)
        
        ai_parser = ai.get_argparser()
        ai_args = ai_parser.parse_args(patch_arg_list)
        ai.fix(ai_args)
        DEBUG_REPLACE_PATCH(DEBUG_PATCH, patch_location)
        build_log_path_2 = builder.build_packages(builder_args)
        build_success_2, failed_package_2 = patch_verifier.check(build_log_path_2)
        
        if not build_success_2:
            print("unable to resolve.")
        else:
            print("Patch Sucessfully resolved Build Error.")


g.close()