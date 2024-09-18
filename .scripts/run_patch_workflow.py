import os
import shutil
import builder

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
target_file = "vinca_linux_64.yaml"



recipes_dir = "../recipes"
source_vinca = f"./{target_file}"
target_vinca = f"../vinca.yaml"
shutil.copyfile(source_vinca, target_vinca)

insert_after_category(target_vinca,"skip_existing:", skip_existing_flag)
arg_list = ['-s', './']
builder_parser = builder.get_argparser()
builder_args =  builder_parser.parse_args(arg_list)
build_log_path = builder.run_all(builder_args)
build_success, failed_package = patch_verifier.check(build_log_path)
print(f"Built Successfully: {build_success}")