import datetime
import shutil
import os
import re
import stat

from ruamel import yaml
from pathlib import Path

from vinca.utils import get_pkg_build_number

TEMPLATE = """\
# yaml-language-server: $schema=https://raw.githubusercontent.com/prefix-dev/recipe-format/main/schema.json

package:
  name: ros
  version: 0.0.1

source:

build:
  number: 0

about:
  homepage: https://www.ros.org/
  license: BSD-3-Clause
  summary: |
    Robot Operating System

extra:
  recipe-maintainers:
    - ros-forge

"""

post_process_items = [
    {
        "files": ["*.pc"],
        "regex": '(?:-L|-I)?"?([^;\\s]+/sysroot/)',
        "replacement": "$$(CONDA_BUILD_SYSROOT_S)",
    },
    {
        "files": ["*.cmake"],
        "regex": '([^;\\s"]+/sysroot)',
        "replacement": "$$ENV{CONDA_BUILD_SYSROOT}",
    },
    {
        "files": ["*.cmake"],
        "regex": '([^;\\s"]+/MacOSX\\d*\\.?\\d*\\.sdk)',
        "replacement": "$$ENV{CONDA_BUILD_SYSROOT}",
    },
]


def write_recipe_package(recipe):
    file = yaml.YAML()
    file.width = 4096
    file.indent(mapping=2, sequence=4, offset=2)

    os.makedirs(recipe["package"]["name"], exist_ok=True)
    recipe_path = os.path.join(recipe["package"]["name"], "recipe.yaml")
    with open(recipe_path, "w") as stream:
        file.dump(recipe, stream)


def copyfile_with_exec_permissions(source_file, destination_file):
    shutil.copyfile(source_file, destination_file)

    # It seems that rattler-build requires script to have executable permissions
    if os.name == "posix":
        # Retrieve current permissions
        current_permissions = os.stat(destination_file).st_mode
        # Set executable permissions for user, group, and others
        os.chmod(
            destination_file,
            current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
        )


def write_recipe(source, outputs, vinca_conf, single_file=True):
    # single_file = False
    if single_file:
        file = yaml.YAML()
        file.width = 4096
        file.indent(mapping=2, sequence=4, offset=2)
        meta = file.load(TEMPLATE)

        meta["source"] = [source[k] for k in source]
        meta["outputs"] = outputs
        meta["package"]["version"] = f"{datetime.datetime.now():%Y.%m.%d}"
        meta["recipe"] = meta["package"]
        del meta["package"]
        meta["build"]["number"] = vinca_conf.get("build_number", 0)
        meta["build"]["post_process"] = post_process_items
        with open("recipe.yaml", "w") as stream:
            file.dump(meta, stream)
    else:
        for o in outputs:
            file = yaml.YAML()
            file.width = 4096
            file.indent(mapping=2, sequence=4, offset=2)
            meta = file.load(TEMPLATE)

            # safe lookup of source entry; dummy recipes may not have a source
            # only include source section if entry is present, else remove it (dummy recipes)
            src_entry = source.get(o["package"]["name"], {})
            if src_entry:
                meta["source"] = src_entry
            else:
                meta.pop("source", None)
            for k, v in o.items():
                meta[k] = v

            meta["package"]["name"] = o["package"]["name"]
            meta["package"]["version"] = o["package"]["version"]

            meta["build"]["number"] = get_pkg_build_number(
                vinca_conf.get("build_number", 0), o["package"]["name"], vinca_conf
            )
            meta["build"]["post_process"] = post_process_items

            if test := vinca_conf["_tests"].get(o["package"]["name"]):
                print("Using test: ", test)
                text = test.read_text()
                test_content = yaml.safe_load(text)
                meta["tests"] = test_content["tests"]

            recipe_dir = (Path("recipes") / o["package"]["name"]).absolute()
            os.makedirs(recipe_dir, exist_ok=True)

            # Copy test folder contents if corresponding test folder exists
            test_dir = vinca_conf.get("_test_dir")
            if test_dir is not None:
                test_folder_name = o["package"]["name"]
                test_folder_path = test_dir / test_folder_name

                if test_folder_path.exists() and test_folder_path.is_dir():
                    # Copy all contents of the test folder to the recipe directory
                    for item in test_folder_path.iterdir():
                        if item.is_file():
                            shutil.copy2(item, recipe_dir / item.name)
                        elif item.is_dir():
                            # Use copytree for directories, but handle existing directories
                            dest_dir = recipe_dir / item.name
                            if dest_dir.exists():
                                shutil.rmtree(dest_dir)
                            shutil.copytree(item, dest_dir)

            with open(recipe_dir / "recipe.yaml", "w") as stream:
                file.dump(meta, stream)

            if meta.get("source") and meta["source"].get("patches"):
                for p in meta["source"]["patches"]:
                    patch_dir, _ = os.path.split(p)
                    os.makedirs(recipe_dir / patch_dir, exist_ok=True)
                    shutil.copyfile(p, recipe_dir / p)

            build_scripts = re.findall(r"'(.*?)'", meta["build"]["script"])
            for script in build_scripts:
                script_filename = (
                    script.replace("$RECIPE_DIR", "")
                    .replace("%RECIPE_DIR%", "")
                    .replace("/", "")
                    .replace("\\", "")
                )
                # Generate the build script directly in the recipe directory
                # Get additional CMake arguments from pkg_additional_info
                from vinca.utils import (
                    get_pkg_additional_info,
                    ensure_name_is_without_distro_prefix_and_with_underscores,
                )

                pkg_name = o["package"]["name"]
                # Use the proper utility function to normalize the package name
                pkg_shortname = (
                    ensure_name_is_without_distro_prefix_and_with_underscores(
                        pkg_name, vinca_conf
                    )
                )

                additional_cmake_args = ""
                additional_folder = ""
                if pkg_shortname:
                    pkg_additional_info = get_pkg_additional_info(
                        pkg_shortname, vinca_conf
                    )
                    additional_cmake_args = pkg_additional_info.get(
                        "additional_cmake_args", ""
                    )

                    # Check if this package has folder info from additional_packages_snapshot
                    if (
                        vinca_conf.get("_additional_packages_snapshot")
                        and pkg_shortname in vinca_conf["_additional_packages_snapshot"]
                    ):
                        additional_folder = vinca_conf["_additional_packages_snapshot"][
                            pkg_shortname
                        ].get("additional_folder", "")

                generate_build_script_for_recipe(
                    script_filename,
                    recipe_dir / script_filename,
                    additional_cmake_args,
                    additional_folder,
                )
            if "catkin" in o["package"]["name"] or "workspace" in o["package"]["name"]:
                # Generate activation scripts directly in the recipe directory
                generate_activation_scripts_for_recipe(recipe_dir)


def generate_template(template_in, template_out, extra_globals=None):
    import em
    from vinca.config import skip_testing, ros_distro

    g = {"ros_distro": ros_distro, "skip_testing": "ON" if skip_testing else "OFF"}

    # Merge additional global variables if provided
    if extra_globals:
        g.update(extra_globals)

    interpreter = em.Interpreter(
        output=template_out, options={em.RAW_OPT: True, em.BUFFERED_OPT: True}
    )
    interpreter.updateGlobals(g)
    interpreter.file(open(template_in))
    interpreter.shutdown()

    # It seems that rattler-build requires script to have executable permissions
    # See https://github.com/RoboStack/ros-humble/pull/229#issuecomment-2549988298
    if os.name == "posix":
        # Retrieve current permissions
        current_permissions = os.stat(template_out.name).st_mode
        # Set executable permissions for user, group, and others
        os.chmod(
            template_out.name,
            current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
        )


def generate_build_script_for_recipe(
    script_name, output_path, additional_cmake_args="", additional_folder=""
):
    """Generate a specific build script directly in the recipe directory."""
    import pkg_resources

    # Map script names to their template files
    script_templates = {
        "build_ament_cmake.sh": "templates/build_ament_cmake.sh.in",
        "bld_ament_cmake.bat": "templates/bld_ament_cmake.bat.in",
        "build_ament_python.sh": "templates/build_ament_python.sh.in",
        "bld_ament_python.bat": "templates/bld_ament_python.bat.in",
        "build_catkin.sh": "templates/build_catkin.sh.in",
        "bld_catkin.bat": "templates/bld_catkin.bat.in",
        "bld_colcon_merge.bat": "templates/bld_colcon_merge.bat.in",
        "bld_catkin_merge.bat": "templates/bld_catkin_merge.bat.in",
    }

    if script_name in script_templates:
        template_in = pkg_resources.resource_filename(
            "vinca", script_templates[script_name]
        )
        with open(output_path, "w") as output_file:
            extra_globals = {}
            if additional_cmake_args:
                extra_globals["additional_cmake_args"] = additional_cmake_args
            else:
                extra_globals["additional_cmake_args"] = ""
            if additional_folder:
                extra_globals["additional_folder"] = additional_folder
            else:
                extra_globals["additional_folder"] = ""
            generate_template(template_in, output_file, extra_globals)

        # Set executable permissions on Unix systems
        if os.name == "posix" and script_name.endswith(".sh"):
            current_permissions = os.stat(output_path).st_mode
            os.chmod(
                output_path,
                current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
            )
    else:
        print(f"Warning: Unknown build script template for {script_name}")


def generate_activation_scripts_for_recipe(recipe_dir):
    """Generate activation scripts directly in the recipe directory."""
    import pkg_resources

    activation_templates = {
        "activate.sh": "templates/activate.sh.in",
        "activate.bat": "templates/activate.bat.in",
        "activate.ps1": "templates/activate.ps1.in",
        "deactivate.sh": "templates/deactivate.sh.in",
        "deactivate.bat": "templates/deactivate.bat.in",
        "deactivate.ps1": "templates/deactivate.ps1.in",
    }

    for script_name, template_path in activation_templates.items():
        template_in = pkg_resources.resource_filename("vinca", template_path)
        output_path = recipe_dir / script_name
        with open(output_path, "w") as output_file:
            generate_template(
                template_in, output_file
            )  # No extra globals needed for activation scripts

        # Set executable permissions on Unix systems for shell scripts
        if os.name == "posix" and script_name.endswith(".sh"):
            current_permissions = os.stat(output_path).st_mode
            os.chmod(
                output_path,
                current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
            )
