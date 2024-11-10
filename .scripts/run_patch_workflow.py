"""
This module manages and deploys a patching workflow for building and resolving errors in RoboStack.

It provides functionalities to:
1. Parse command-line arguments for configuring access to the LLM Model API.
2. Analyze and isolate build errors from logs.
3. Download a copy of the identified failing package
4. Apply Large Language Model fixes to scripts causing build errors and generate patches for those fixes.
5. Verify the build results.

Dependencies:
- Python modules: os, shutil, argparse, re, time, git
- Custom modules: builder, patch_verifier, robostack_AI

Usage:
Run the script with appropriate command-line arguments to initiate the patching workflow.

Example:
    python run_patch_workflow.py -ip <API_IP> -p <PORT> -d -s <SKIP_EXISTING_DIR> -m <MODEL_NAME>
"""

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
    """
    Parses command-line arguments for configuring access to the LLM Model API and controlling script behavior.

    Returns:
        argparse.Namespace: An object containing the parsed command-line arguments as attributes.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-ip', '--ip', type=str, required=True, help="IP Address for Accessing LLM Model API")
    parser.add_argument("-p", "--port", type=str, default="11434")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Stops any changes from occuring to RoboStack")
    parser.add_argument('-s', '--skip_existing', type=str, default=None, help="The Skip existing directory for packages that won't be checked for failing builds. Used for faster build times")
    parser.add_argument('-m', '--model', type=str, default='llama3.1')
    return parser.parse_args()

def filter_strings(strings, substring):
    """
    Filters out strings from the input list that contain the specified substring.

    Args:
        strings (list of str): The list of strings to be filtered.
        substring (str): The substring to check for exclusion.

    Returns:
        list of str: A new list containing strings that do not include the specified substring.
    """
    return [s for s in strings if substring not in s]

def extract_file_paths(log_content):
    """
    Extracts file paths from the provided log content.

    This function searches for sequences in the log content that resemble file paths,
    specifically those containing at least one '/' character, and returns them as a list.

    Args:
        log_content (str): The log content from which to extract file paths.

    Returns:
        list of str: A list containing the extracted file paths.
    """
    path_pattern = r'(?:^|\s)(\S+/\S+)'
    matches = re.findall(path_pattern, log_content)
    return matches

def split_and_filter_string(strings, split_string):
    """
    Splits each string in the input list at the first occurrence of the specified delimiter
    and extracts the last segment. Strings that do not contain the delimiter are excluded.

    Args:
        strings (list of str): The list of strings to process.
        split_string (str): The delimiter to split each string.

    Returns:
        list of str: A list containing the last segments of the split strings.
    """
    def extract_single_path(path):
        parts = path.split(split_string)
        return parts[-1] if len(parts) > 1 else None

    extracted = [extract_single_path(dir) for dir in strings]
    return [path for path in extracted if path is not None]

def isolate_build_error(package, log_path):
    """
    Isolates the build error section for a specified package from a build log.

    This function reads a build log file, extracts the segment corresponding to the
    build process of the specified package, identifies file paths within this segment,
    filters them based on predefined criteria, and verifies their existence in a
    temporary directory structure.

    Args:
        package (str): The name of the package whose build error is to be isolated.
        log_path (str): The file path to the build log.

    Returns:
        tuple:
            - str: The isolated segment of the log corresponding to the package's build process.
            - list of str: A list of absolute file paths that exist in the temporary directory structure.

    Raises:
        FileNotFoundError: If the specified log file does not exist.
        IOError: If there is an error reading the log file.
    """
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
    """
    Removes the 'patch' directory for the specified package's recipe.

    This function constructs the path to the 'patch' directory within the package's
    recipe directory and deletes it along with all its contents.

    Args:
        package_name (str): The name of the package whose 'patch' directory is to be removed.

    Raises:
        FileNotFoundError: If the 'patch' directory does not exist.
        PermissionError: If the operation lacks the necessary permissions to delete the directory.
    """
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
    """
    Replaces the contents of the specified file with new content.

    This function deletes the existing file at the target path and creates a new file
    with the same name, writing the provided content to it.

    Args:
        content (str): The new content to write to the file.
        target (str): The path to the target file to be replaced.

    Raises:
        FileNotFoundError: If the target file does not exist.
        PermissionError: If the operation lacks the necessary permissions to delete or write to the file.
        OSError: For other errors such as the file being in use or filesystem-related issues.
    """
    os.remove(target)
    with open(target,"w") as target_file:
        target_file.write(content)

def insert_after_category(file_path, category_name, added_insert):
    """
    Inserts a specified line of text immediately after the first occurrence of a line containing the given category name in a file.

    Args:
        file_path (str): The path to the file to be modified.
        category_name (str): The category name to search for within the file.
        added_insert (str): The line of text to insert after the category line.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        IOError: If there is an error reading from or writing to the file.
    """
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
    """
    Retrieves and prepares the source code of the specified package for building.

    This function performs the following steps:
    1. Extracts the Git repository URL and revision from the package's recipe file.
    2. Cleans the temporary directory to ensure a fresh environment.
    3. Clones the repository and checks out the specified revision.
    4. Applies the package's patch file to the cloned repository.
    5. Isolates build errors related to the package by analyzing the build log.

    Args:
        package_name (str): The name of the package to process.
        log_path (str): The path to the build log file.

    Returns:
        tuple:
            - str: The filtered log segment related to the package's build process.
            - list of str: Potential file paths associated with the build error.
            - git.Repo: The Git repository object of the cloned package.

    Raises:
        FileNotFoundError: If the recipe or patch file does not exist.
        GitCommandError: If there is an error during Git operations.
        Exception: For other unforeseen errors.
    """
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
    """
    Executes the package build process, verifies the build results, and applies patches to resolve build errors.

    This function performs the following steps:
    1. Copies the source Vinca configuration file to the target location.
    2. Modifies the build configuration to skip existing packages if specified.
    3. Initiates the build process and logs the build results.
    4. Verifies the build outcomes and identifies any failed packages.
    5. If a build failure is detected:
       a. Fetches the relevant script and isolates the build error.
       b. Applies AI-driven fixes to the problematic script.
       c. Generates a patch based on the fixes and replaces the existing patch file.
       d. Rebuilds the packages and verifies the build results.
       e. If the build is successful, updates the patch directory with the new patch.

    Args:
        args (argparse): The command-line arguments containing configuration options. Use parse_arguments

    Returns:
        list: A list of timestamps indicating the start time of each major step in the process.

    Raises:
        Exception: If the build error cannot be resolved after applying patches.
    """
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
            ai.fix(args=args, bad_script_path=target_script,error_log=filtered_log)
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
