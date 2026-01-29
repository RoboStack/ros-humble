#!/usr/bin/env python

import argparse
import catkin_pkg
import sys
import os
import glob
import platform
import ruamel.yaml
from pathlib import Path

from vinca import __version__
from .resolve import get_conda_index
from .resolve import resolve_pkgname
from .template import write_recipe, write_recipe_package
from .distro import Distro
from .v1_selectors import evaluate_selectors

from vinca import config
from vinca.utils import (
    get_repodata,
    get_pkg_build_number,
    get_pkg_additional_info,
    is_dummy_metapackage,
)
from vinca.license_utils import convert_to_spdx_license

unsatisfied_deps = set()
distro = None


def ensure_list(obj):
    if not obj:
        return []
    assert isinstance(obj, list)
    return obj


def get_conda_subdir():
    if config.parsed_args.platform:
        return config.parsed_args.platform

    sys_platform = sys.platform
    machine = platform.machine()
    if sys_platform.startswith("linux"):
        if machine == "aarch64":
            return "linux-aarch64"
        elif machine == "x86_64":
            return "linux-64"
        else:
            raise RuntimeError("Unknown machine!")
    elif sys_platform == "darwin":
        if machine == "arm64":
            return "osx-arm64"
        else:
            return "osx-64"
    elif sys_platform == "win32":
        return "win-64"


def parse_command_line(argv):
    """
    Parse command line argument. See -h option.
    :param argv: the actual program arguments
    :return: parsed arguments
    """
    import textwrap

    default_dir = "."

    example = textwrap.dedent(
        """
      Examples:
        {0} -d ./examples/
      See: https://github.com/RoboStack/vinca
    """
    ).format(os.path.basename(argv[0]))
    formatter_class = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        description="Conda recipe generator for ROS packages",
        epilog=example,
        formatter_class=formatter_class,
    )
    parser.add_argument(
        "-V", "--version", action="version", version="%(prog)s {}".format(__version__)
    )
    parser.add_argument(
        "-d",
        "--dir",
        dest="dir",
        default=default_dir,
        help="The directory to process (default: {}).".format(default_dir),
    )
    parser.add_argument(
        "-s",
        "--skip",
        dest="skip_already_built_repodata",
        default=[],
        help="Skip already built from repodata.",
    )
    parser.add_argument(
        "-m",
        "--multiple",
        dest="multiple_file",
        action="store_const",
        const=True,
        default=False,
        help="Create one recipe for package.",
    )
    parser.add_argument(
        "-n",
        "--trigger-new-versions",
        dest="trigger_new_versions",
        action="store_const",
        const=True,
        default=False,
        help="Trigger the build of packages that have new versions available.",
    )
    parser.add_argument(
        "--source",
        dest="source",
        action="store_const",
        const=True,
        default=False,
        help="Create recipe with develop repo.",
    )
    parser.add_argument(
        "-p", "--package", dest="package", default=None, help="The package.xml path."
    )
    parser.add_argument(
        "--platform",
        dest="platform",
        default=None,
        help="The conda platform to check existing recipes for.",
    )
    arguments = parser.parse_args(argv[1:])
    global selected_platform
    config.parsed_args = arguments
    config.selected_platform = get_conda_subdir()
    return arguments


def get_depmods(vinca_conf, pkg_name):
    depmods = vinca_conf["depmods"].get(pkg_name, {})
    rm_deps, add_deps = (
        {"build": [], "host": [], "run": []},
        {"build": [], "host": [], "run": []},
    )

    for dep_type in ["build", "host", "run"]:
        if depmods.get("remove_" + dep_type):
            for el in depmods["remove_" + dep_type]:
                if isinstance(el, dict):
                    rm_deps[dep_type].append(dict(el))
                else:
                    rm_deps[dep_type].append(el)

        if depmods.get("add_" + dep_type):
            for el in depmods["add_" + dep_type]:
                if isinstance(el, dict):
                    add_deps[dep_type].append(dict(el))
                else:
                    add_deps[dep_type].append(el)
    return rm_deps, add_deps


def read_vinca_yaml(filepath):
    yaml = ruamel.yaml.YAML()
    vinca_conf = evaluate_selectors(
        yaml.load(open(filepath, "r")), target_platform=get_conda_subdir()
    )

    # normalize paths to absolute paths
    conda_index = []
    for i in vinca_conf["conda_index"]:
        if os.path.isfile(i):
            conda_index.append(os.path.abspath(i))
        else:
            conda_index.append(i)

    vinca_conf["conda_index"] = conda_index
    patch_dir = Path(vinca_conf["patch_dir"]).absolute()
    vinca_conf["_patch_dir"] = patch_dir
    patches = {}

    for x in glob.glob(os.path.join(vinca_conf["_patch_dir"], "*.patch")):
        splitted = os.path.basename(x).split(".")
        if splitted[0] not in patches:
            patches[splitted[0]] = {
                "any": [],
                "osx": [],
                "linux": [],
                "win": [],
                "emscripten": [],
            }
        if len(splitted) == 3:
            if splitted[1] in ("osx", "linux", "win", "emscripten"):
                patches[splitted[0]][splitted[1]].append(x)
                continue
            if splitted[1] == "unix":
                patches[splitted[0]]["linux"].append(x)
                patches[splitted[0]]["osx"].append(x)
                continue

        patches[splitted[0]]["any"].append(x)

    vinca_conf["_patches"] = patches

    tests = {}
    test_dir = Path(filepath).parent / "tests"
    # Store the test directory directly for use in template.py
    vinca_conf["_test_dir"] = test_dir
    for x in test_dir.glob("*.yaml"):
        tests[os.path.basename(x).split(".")[0]] = x
    vinca_conf["_tests"] = tests

    if (patch_dir / "dependencies.yaml").exists():
        vinca_conf["depmods"] = evaluate_selectors(
            yaml.load(open(patch_dir / "dependencies.yaml")),
            target_platform=get_conda_subdir(),
        )
    if not vinca_conf.get("depmods"):
        vinca_conf["depmods"] = {}

    config.ros_distro = vinca_conf["ros_distro"]
    config.skip_testing = vinca_conf.get("skip_testing", True)

    vinca_conf["_conda_indexes"] = get_conda_index(
        vinca_conf, os.path.dirname(filepath)
    )

    vinca_conf["trigger_new_versions"] = vinca_conf.get("trigger_new_versions", False)

    if (Path(filepath).parent / "pkg_additional_info.yaml").exists():
        vinca_conf["_pkg_additional_info"] = evaluate_selectors(
            yaml.load(open(Path(filepath).parent / "pkg_additional_info.yaml")),
            target_platform=get_conda_subdir(),
        )
    else:
        vinca_conf["_pkg_additional_info"] = {}

    # snapshot contains both rosdistro_snapshot.yaml and
    # rosdistro_additional_recipes.yaml
    snapshot, additional_packages_snapshot = read_snapshot(vinca_conf)

    # Store additional_packages_snapshot in vinca_conf for template access
    vinca_conf["_snapshot"] = snapshot or {}
    vinca_conf["_additional_packages_snapshot"] = additional_packages_snapshot or {}

    return vinca_conf


def read_snapshot(vinca_conf):
    if "rosdistro_snapshot" not in vinca_conf:
        return None, None

    yaml = ruamel.yaml.YAML()
    # load primary snapshot
    snapshot = yaml.load(open(vinca_conf["rosdistro_snapshot"], "r")) or {}
    # if additional snapshot file specified, load and merge
    additional_key = "rosdistro_additional_recipes"
    additional = None
    if additional_key in vinca_conf and vinca_conf[additional_key]:
        additional = yaml.load(open(vinca_conf[additional_key], "r")) or {}
        # merge additional entries, overriding or adding
        snapshot.update(additional)

    return snapshot, additional


def generate_output(pkg_shortname, vinca_conf, distro, version, all_pkgs=None):
    if not all_pkgs:
        all_pkgs = []

    if pkg_shortname not in vinca_conf["_selected_pkgs"]:
        return None

    pkg_names = resolve_pkgname(pkg_shortname, vinca_conf, distro)
    if not pkg_names:
        return None

    if vinca_conf.get("trigger_new_versions"):
        if (pkg_names[0], version) in vinca_conf["skip_built_packages"]:
            return None
    else:
        if pkg_names[0] in vinca_conf["skip_built_packages"]:
            return None
    # handle dummy recipe generation for vendored packages
    output = {}
    if is_dummy_metapackage(pkg_shortname, vinca_conf):
        pkg_additional_info = get_pkg_additional_info(pkg_shortname, vinca_conf)
        gen = pkg_additional_info["generate_dummy_package_with_run_deps"]
        dep_name = gen.get("dep_name")
        # dep_name is required to specify which dependency to pin in the dummy recipe
        if not dep_name:
            runerr = f"Missing 'dep_name' for dummy recipe of {pkg_shortname}"
            raise RuntimeError(runerr)
        # upper_bound is required for dummy recipe pinning
        upper_bound = gen.get("upper_bound")
        if not upper_bound:
            upper_bound = gen.get("max_pin")
            if not upper_bound:
                runerr = f"Missing 'upper_bound' or 'max_pin' for dummy recipe of {pkg_shortname}"
                raise RuntimeError(runerr)
        # Compute rattler-build-compatible version constraint based on upper_bound:
        # - lower bound: allow the exact package version (or override_version if specified)
        # - upper bound: increment the segment of version defined by upper_bound length,
        #   then append 'a0' to ensure the constraint captures pre-releases correctly

        # Use override_version if specified, otherwise use the ROS package version
        dummy_package_version = gen.get("override_version", version)
        lower = dummy_package_version
        parts = [int(p) for p in lower.split(".")]
        seg = len(upper_bound.split("."))
        upper_parts = parts[:seg]
        upper_parts[-1] += 1
        upper_parts += [0] * (len(parts) - seg)
        upper = ".".join(str(p) for p in upper_parts) + "a0"
        constraint = f"{dep_name} >={lower}, <{upper}"
        output = {
            "package": {"name": pkg_names[0], "version": dummy_package_version},
            "build": {
                "number": get_pkg_build_number(
                    vinca_conf.get("build_number", 0), pkg_names[0], vinca_conf
                ),
                "script": "",
            },
            "requirements": {"build": [], "host": [], "run": [constraint]},
        }
    else:
        # If the package is not a dummy recipe, we generate a full recipe
        output = {
            "package": {"name": pkg_names[0], "version": version},
            "requirements": {
                "build": [
                    "${{ compiler('cxx') }}",
                    "${{ compiler('c') }}",
                    {
                        "if": "target_platform!='emscripten-wasm32'",
                        "then": ["${{ stdlib('c') }}"],
                    },
                    "ninja",
                    "python",
                    "setuptools",
                    "git",
                    "git-lfs",
                    {"if": "unix", "then": ["patch", "make", "coreutils"]},
                    {"if": "win", "then": ["m2-patch"]},
                    {"if": "osx", "then": ["tapi"]},
                    {"if": "build_platform != target_platform", "then": ["pkg-config"]},
                    "cmake",
                    "cython",
                    {
                        "if": "build_platform != target_platform",
                        "then": [
                            "python",
                            "cross-python_${{ target_platform }}",
                            "numpy",
                        ],
                    },
                ],
                "host": [
                    {"if": "build_platform == target_platform", "then": ["pkg-config"]},
                    "python",
                    "numpy",
                    "pip",
                ],
                "run": [],
            },
            "build": {"script": ""},
        }

    xml = distro.get_release_package_xml(pkg_shortname)

    # If the snapshot is not aligned with the latest rosdistro (for example if a package is removed,
    # see https://github.com/RoboStack/ros-jazzy/pull/107#issuecomment-3338962041), get_release_package_xml can return none,
    # in that case we can just skip the package, remove if https://github.com/RoboStack/vinca/issues/93 is fixed
    if not xml:
        print(
            "Skip "
            + pkg_shortname
            + " as it is present in our snapshot, but not in the latest rosdistro cache."
        )
        return None

    pkg = catkin_pkg.package.parse_package_string(xml)

    pkg.evaluate_conditions(os.environ)

    resolved_python = resolve_pkgname("python", vinca_conf, distro)
    output["requirements"]["run"].extend(resolved_python)
    output["requirements"]["host"].extend(resolved_python)

    if is_dummy_metapackage(pkg_shortname, vinca_conf):
        # Dummy recipes do not actually build anything, so we set the script to empty
        output["build"]["script"] = ""
    elif pkg.get_build_type() in ["cmake", "catkin"]:
        output["build"]["script"] = (
            "${{ '$RECIPE_DIR/build_catkin.sh' if unix or wasm32 else '%RECIPE_DIR%\\\\bld_catkin.bat' }}"
        )
    elif pkg.get_build_type() in ["ament_cmake"]:
        output["build"]["script"] = (
            "${{ '$RECIPE_DIR/build_ament_cmake.sh' if unix or wasm32 else '%RECIPE_DIR%\\\\bld_ament_cmake.bat' }}"
        )
    elif pkg.get_build_type() in ["ament_python"]:
        output["build"]["script"] = (
            "${{ '$RECIPE_DIR/build_ament_python.sh' if unix or wasm32 else '%RECIPE_DIR%\\\\bld_ament_python.bat' }}"
        )
        resolved_setuptools = resolve_pkgname("python-setuptools", vinca_conf, distro)
        output["requirements"]["host"].extend(resolved_setuptools)
    else:
        print(f"Unknown build type for {pkg_shortname}: {pkg.get_build_type()}")
        return None

    if vinca_conf.get("mutex_package"):
        mutex_dep = get_mutex_package_dependency(vinca_conf, distro)
        if mutex_dep:
            output["requirements"]["host"].append(mutex_dep)
            output["requirements"]["run"].append(mutex_dep)

    if not distro.check_ros1() and pkg_shortname not in [
        "ament_cmake_core",
        "ament_package",
        "ros_workspace",
        "ros_environment",
    ]:
        output["requirements"]["host"].append(
            f"ros-{config.ros_distro}-ros-environment"
        )
        output["requirements"]["host"].append(f"ros-{config.ros_distro}-ros-workspace")
        output["requirements"]["run"].append(f"ros-{config.ros_distro}-ros-workspace")

    rm_deps, add_deps = get_depmods(vinca_conf, pkg.name)
    gdeps = []
    if pkg.group_depends:
        for gdep in pkg.group_depends:
            gdep.extract_group_members(all_pkgs)
            gdeps += gdep.members

    build_tool_deps = pkg.buildtool_depends
    build_tool_deps += pkg.buildtool_export_depends
    build_tool_deps = [d.name for d in build_tool_deps if d.evaluated_condition]

    build_deps = pkg.build_depends
    build_deps += pkg.build_export_depends
    build_deps += pkg.test_depends
    build_deps = [d.name for d in build_deps if d.evaluated_condition]
    build_deps += gdeps

    # we stick some build tools into the `build` section to make cross compilation work
    # right now it's only `git`.
    for dep in build_tool_deps:
        resolved_dep = resolve_pkgname(dep, vinca_conf, distro)
        if not resolved_dep:
            unsatisfied_deps.add(dep)
            continue

        if "git" in resolved_dep:
            output["requirements"]["build"].extend(resolved_dep)
        else:
            # remove duplicate cmake
            if dep not in ["cmake"]:
                build_deps.append(dep)

        # Hack to add cyclonedds into build for cross compilation
        if pkg_shortname == "cyclonedds" or "cyclonedds" in (
            build_deps + build_tool_deps
        ):
            output["requirements"]["build"].append(
                {
                    "if": "build_platform != target_platform",
                    "then": [f"ros-{config.ros_distro}-cyclonedds"],
                }
            )

    for dep in build_deps:
        resolved_dep = resolve_pkgname(dep, vinca_conf, distro)
        if not resolved_dep:
            unsatisfied_deps.add(dep)
            continue
        output["requirements"]["host"].extend(resolved_dep)

    run_deps = pkg.run_depends
    run_deps += pkg.exec_depends
    run_deps += pkg.build_export_depends
    run_deps += pkg.buildtool_export_depends
    run_deps = [d.name for d in run_deps if d.evaluated_condition]
    run_deps += gdeps

    for dep in run_deps:
        resolved_dep = resolve_pkgname(dep, vinca_conf, distro, is_rundep=True)
        if not resolved_dep:
            unsatisfied_deps.add(dep)
            continue
        output["requirements"]["run"].extend(resolved_dep)

    for dep_type in ["build", "host", "run"]:
        for dep in add_deps[dep_type]:
            output["requirements"][dep_type].append(dep)
        for dep in rm_deps[dep_type]:
            while dep in output["requirements"][dep_type]:
                output["requirements"][dep_type].remove(dep)

    def sortkey(k):
        if isinstance(k, dict):
            return list(k.values())[0]
        return k

    # For Emscripten, only install cmake as a build dependency.
    # This should be ok as cmake is only really needed during builds, not when running packages.
    if "cmake" in output["requirements"]["run"]:
        output["requirements"]["run"].remove("cmake")
        output["requirements"]["run"].append(
            {"if": "target_platform != 'emscripten-wasm32'", "then": ["cmake"]}
        )

    if "cmake" in output["requirements"]["host"]:
        output["requirements"]["host"].remove("cmake")
        if "cmake" not in output["requirements"]["build"]:
            output["requirements"]["build"].append("cmake")

    if f"ros-{config.ros_distro}-mimick-vendor" in output["requirements"]["build"]:
        output["requirements"]["build"].remove(f"ros-{config.ros_distro}-mimick-vendor")
        output["requirements"]["build"].append(
            {
                "if": "target_platform != 'emscripten-wasm32'",
                "then": [f"ros-{config.ros_distro}-mimick-vendor"],
            }
        )

    if f"ros-{config.ros_distro}-mimick-vendor" in output["requirements"]["host"]:
        output["requirements"]["host"].remove(f"ros-{config.ros_distro}-mimick-vendor")
        output["requirements"]["build"].append(
            {
                "if": "target_platform != 'emscripten-wasm32'",
                "then": [f"ros-{config.ros_distro}-mimick-vendor"],
            }
        )

    if (
        f"ros-{config.ros_distro}-rosidl-default-generators"
        in output["requirements"]["host"]
    ):
        output["requirements"]["build"].append(
            {
                "if": "target_platform == 'emscripten-wasm32'",
                "then": [f"ros-{config.ros_distro}-rosidl-default-generators"],
            }
        )

    output["requirements"]["run"] = sorted(output["requirements"]["run"], key=sortkey)
    output["requirements"]["host"] = sorted(output["requirements"]["host"], key=sortkey)

    output["requirements"]["run"] += [
        {
            "if": "osx and x86_64",
            "then": ["__osx >=${{ MACOSX_DEPLOYMENT_TARGET|default('10.14') }}"],
        }
    ]

    if f"ros-{config.ros_distro}-pybind11-vendor" in output["requirements"]["host"]:
        output["requirements"]["host"] += ["pybind11"]
    if "pybind11" in output["requirements"]["host"]:
        output["requirements"]["build"] += [
            {"if": "build_platform != target_platform", "then": ["pybind11"]}
        ]
    if "qt-main" in output["requirements"]["host"]:
        output["requirements"]["build"] += [
            {"if": "build_platform != target_platform", "then": ["qt-main"]}
        ]
    # pyqt-builder + git + doxygen must be in build, not host for cross-compile
    pkgs_move_to_build = ["pyqt-builder", "git", "doxygen", "git-lfs"]
    for pkg_move_to_build in pkgs_move_to_build:
        if pkg_move_to_build in output["requirements"]["host"]:
            output["requirements"]["build"] += [
                {"if": "build_platform != target_platform", "then": [pkg_move_to_build]}
            ]
            while pkg_move_to_build in output["requirements"]["host"]:
                output["requirements"]["host"].remove(pkg_move_to_build)
            output["requirements"]["host"] += [
                {"if": "build_platform == target_platform", "then": [pkg_move_to_build]}
            ]

    # remove duplicates
    for dep_type in ["build", "host", "run"]:
        tmp_nonduplicate = []
        [
            tmp_nonduplicate.append(x)
            for x in output["requirements"][dep_type]
            if x not in tmp_nonduplicate
        ]
        output["requirements"][dep_type] = tmp_nonduplicate

    # Add "about" section with license and package metadata
    output["about"] = {}

    # Add URLs from package.xml based on their type
    for u in pkg.urls:
        if u.type == "website":
            output["about"]["homepage"] = u.url
        elif u.type == "repository":
            output["about"]["repository"] = u.url

    # Add license if available (convert to SPDX format)
    if pkg.licenses:
        spdx_license = convert_to_spdx_license(
            [str(lic) for lic in pkg.licenses], package_name=pkg_shortname
        )
        if spdx_license:
            output["about"]["license"] = spdx_license

    # Add summary/description if available
    if pkg.description:
        output["about"]["summary"] = pkg.description

    return output


def generate_outputs(distro, vinca_conf):
    outputs = []

    def get_pkg(pkg_name):
        pkg = catkin_pkg.package.parse_package_string(
            distro.get_release_package_xml(pkg_name)
        )
        pkg.evaluate_conditions(os.environ)
        return pkg

    all_pkgs = [get_pkg(pkg) for pkg in distro.get_depends("ros_base")]

    for pkg_shortname in vinca_conf["_selected_pkgs"]:
        if not distro.check_package(pkg_shortname):
            print(f"Could not generate output for {pkg_shortname}")
            continue

        try:
            output = generate_output(
                pkg_shortname,
                vinca_conf,
                distro,
                distro.get_version(pkg_shortname),
                all_pkgs,
            )
        except AttributeError:
            print("Skip " + pkg_shortname + " due to invalid version / XML.")
        if output is not None:
            outputs.append(output)

    # Generate mutex package if configured as dictionary
    mutex_recipe = generate_mutex_package_recipe(vinca_conf, distro)
    if mutex_recipe:
        # Check if mutex package should be skipped
        mutex_name = mutex_recipe["package"]["name"]
        mutex_version = mutex_recipe["package"]["version"]

        if should_skip_mutex_package(vinca_conf, mutex_name, mutex_version):
            print(f"Skipping mutex package {mutex_name} (already built)")
        else:
            print(f"Generating mutex package: {mutex_name}")
            outputs.append(mutex_recipe)

    return outputs


def generate_outputs_version(distro, vinca_conf):
    outputs = []
    for pkg_shortname in vinca_conf["_selected_pkgs"]:
        if not distro.check_package(pkg_shortname):
            print(f"Could not generate output for {pkg_shortname}")
            continue

        version = distro.get_version(pkg_shortname)
        output = generate_output(pkg_shortname, vinca_conf, distro, version)
        if output is not None:
            outputs.append(output)

    return outputs


def generate_source(distro, vinca_conf):
    source = {}
    for pkg_shortname in vinca_conf["_selected_pkgs"]:
        if not distro.check_package(pkg_shortname):
            print(f"Could not generate source for {pkg_shortname}")
            continue
        # skip cloning source for dummy recipes
        if is_dummy_metapackage(pkg_shortname, vinca_conf):
            continue
        url, ref, ref_type = distro.get_released_repo(pkg_shortname)
        entry = {}
        entry["git"] = url
        entry[ref_type] = ref
        pkg_names = resolve_pkgname(pkg_shortname, vinca_conf, distro)
        pkg_version = distro.get_version(pkg_shortname)
        print("Checking ", pkg_shortname, pkg_version)
        if not pkg_names:
            continue
        if vinca_conf.get("trigger_new_versions"):
            if (pkg_names[0], pkg_version) in vinca_conf["skip_built_packages"]:
                continue
        else:
            if pkg_names[0] in vinca_conf["skip_built_packages"]:
                continue
        pkg_name = pkg_names[0]
        entry["target_directory"] = "%s/src/work" % pkg_name

        patches = []
        pd = vinca_conf["_patches"].get(pkg_name)
        if pd:
            patches.extend(pd["any"])

            # find specific patches
            plat = get_conda_subdir().split("-")[0]
            patches.extend(pd[plat])
            if len(patches):
                print(patches)
                common_prefix = os.path.commonprefix((os.getcwd(), patches[0]))
                print(common_prefix)
                entry["patches"] = [os.path.relpath(p, common_prefix) for p in patches]

        source[pkg_name] = entry

    # Generate empty source for mutex package (if generated) since it's a meta-package
    mutex_recipe = generate_mutex_package_recipe(vinca_conf, distro)
    if mutex_recipe:
        # Check if mutex package should be skipped
        mutex_name = mutex_recipe["package"]["name"]
        mutex_version = mutex_recipe["package"]["version"]

        if not should_skip_mutex_package(vinca_conf, mutex_name, mutex_version):
            source[mutex_name] = {}

    return source


def generate_source_version(distro, vinca_conf):
    source = {}
    for pkg_shortname in vinca_conf["_selected_pkgs"]:
        if not distro.check_package(pkg_shortname):
            print(f"Could not generate source for {pkg_shortname}")
            continue

        url, ref, ref_type = distro.get_released_repo(pkg_shortname)

        entry = {}
        entry["git"] = url
        entry[ref_type] = ref
        pkg_names = resolve_pkgname(pkg_shortname, vinca_conf, distro)
        version = distro.get_version(pkg_shortname)
        if vinca_conf.get("trigger_new_versions"):
            if (
                not pkg_names
                or (pkg_names[0], version) in vinca_conf["skip_built_packages"]
            ):
                continue
        else:
            if not pkg_names or pkg_names[0] in vinca_conf["skip_built_packages"]:
                continue
        pkg_name = pkg_names[0]
        entry["target_directory"] = "%s/src/work" % pkg_name

        patches = []
        pd = vinca_conf["_patches"].get(pkg_name)
        if pd:
            patches.extend(pd["any"])

            # find specific patches
            plat = get_conda_subdir().split("-")[0]
            patches.extend(pd[plat])
            if len(patches):
                entry["patches"] = patches

        source[pkg_name] = entry

    return source


def generate_fat_source(distro, vinca_conf):
    source = []
    for pkg_shortname in vinca_conf["_selected_pkgs"]:
        if not distro.check_package(pkg_shortname):
            print(f"Could not generate source for {pkg_shortname}")
            continue

        url, ref, ref_type = distro.get_released_repo(pkg_shortname)
        entry = {}
        entry["git"] = url
        entry[ref_type] = ref
        pkg_names = resolve_pkgname(pkg_shortname, vinca_conf, distro)
        if not pkg_names:
            continue
        pkg_name = pkg_names[0]
        entry["target_directory"] = "src/%s" % pkg_name
        patch_path = os.path.join(vinca_conf["_patch_dir"], "%s.patch" % pkg_name)
        if os.path.exists(patch_path):
            entry["patches"] = [
                "%s/%s" % (vinca_conf["patch_dir"], "%s.patch" % pkg_name)
            ]
        source.append(entry)
    return source


def get_selected_packages(distro, vinca_conf):
    selected_packages = set()
    skipped_packages = set()

    if vinca_conf.get("build_all", False):
        selected_packages = set(distro._distro.release_packages.keys())
        # Add packages from rosdistro_additional_recipes.yaml when build_all is True
        if (
            "_additional_packages_snapshot" in vinca_conf
            and vinca_conf["_additional_packages_snapshot"]
        ):
            additional_packages = set(
                vinca_conf["_additional_packages_snapshot"].keys()
            )
            selected_packages = selected_packages.union(additional_packages)
    elif vinca_conf["packages_select_by_deps"]:
        if (
            "packages_skip_by_deps" in vinca_conf
            and vinca_conf["packages_skip_by_deps"] is not None
        ):
            for i in vinca_conf["packages_skip_by_deps"]:
                print(f"Calling replace on {i}.")
                skipped_packages = skipped_packages.union([i, i.replace("-", "_")])
        print("Skipped pkgs: ", skipped_packages)
        for i in vinca_conf["packages_select_by_deps"]:
            i = i.replace("-", "_")
            selected_packages = selected_packages.union([i])
            if i in skipped_packages:
                continue
            try:
                pkgs = distro.get_depends(i, ignore_pkgs=skipped_packages)
            except KeyError as err:
                print(f"KeyError: {err} for package {i}. Skipping.")
                # handle (rare) package names that use "-" as separator
                pkgs = distro.get_depends(i.replace("_", "-"))
                selected_packages.remove(i)
                selected_packages.add(i.replace("_", "-"))
            selected_packages = selected_packages.union(pkgs)

    # Automatically include ros_workspace and ros_environment for ROS2 distributions
    # if any ROS2 packages are selected (these are added as dependencies automatically)
    if not distro.check_ros1() and selected_packages:
        # Check if we have any ROS packages selected (excluding the workspace/environment packages themselves)
        has_ros_packages = any(
            pkg
            not in [
                "ros_workspace",
                "ros_environment",
                "ament_cmake_core",
                "ament_package",
            ]
            for pkg in selected_packages
        )
        if has_ros_packages:
            if distro.check_package("ros_workspace"):
                selected_packages.add("ros_workspace")
            if distro.check_package("ros_environment"):
                selected_packages.add("ros_environment")

    result = sorted(list(selected_packages))
    return result


def parse_mutex_package_config(vinca_conf):
    """Parse and validate mutex package configuration.

    Returns:
        dict: Parsed mutex configuration with all required fields, or None if mutex_package is a string

    Raises:
        ValueError: If mutex_package is a dict but missing required fields
    """
    mutex_pkg = vinca_conf.get("mutex_package")
    if not mutex_pkg:
        return None

    if isinstance(mutex_pkg, str):
        # Backward compatibility: return None to indicate string format
        return None

    if isinstance(mutex_pkg, dict):
        # Validate required fields
        required_fields = ["name", "version", "upper_bound", "run_constraints"]
        missing_fields = [field for field in required_fields if field not in mutex_pkg]

        if missing_fields:
            raise ValueError(
                f"mutex_package configuration is missing required fields: {missing_fields}"
            )

        # Return validated config with build_number from vinca_conf if not specified
        config = dict(mutex_pkg)
        if "build_number" not in config:
            config["build_number"] = vinca_conf.get("build_number", 1)

        return config

    raise ValueError(
        f"mutex_package must be either a string or a dictionary, got {type(mutex_pkg)}"
    )


def get_mutex_package_dependency(vinca_conf, distro):
    """Get the mutex package dependency string, handling both string and dict formats."""
    mutex_pkg = vinca_conf.get("mutex_package")
    if not mutex_pkg:
        return None

    if isinstance(mutex_pkg, str):
        # Backward compatibility: return the string as-is
        return mutex_pkg

    # Try to parse as dict configuration
    try:
        config = parse_mutex_package_config(vinca_conf)
        if config is None:
            # This shouldn't happen since we already checked isinstance(mutex_pkg, str) above
            return None

        # New format: construct the dependency string
        # Compute the pin from version and upper_bound
        version_parts = config["version"].split(".")
        upper_bound_parts = config["upper_bound"].split(".")

        # Take as many version parts as specified by upper_bound
        pin_parts = version_parts[: len(upper_bound_parts)]
        pin = ".".join(pin_parts) + ".*"

        return f"{config['name']} {pin} {distro.name}_*"
    except ValueError as e:
        raise ValueError(f"Error parsing mutex_package configuration: {e}")

    return None


def should_skip_mutex_package(vinca_conf, mutex_name, mutex_version):
    """Check if the mutex package should be skipped based on skip_built_packages logic."""
    if vinca_conf.get("trigger_new_versions"):
        return (mutex_name, mutex_version) in vinca_conf["skip_built_packages"]
    else:
        return mutex_name in vinca_conf["skip_built_packages"]


def generate_mutex_package_recipe(vinca_conf, distro):
    """Generate a mutex package recipe if mutex_package is defined as a dict."""
    try:
        config = parse_mutex_package_config(vinca_conf)
        if config is None:
            # mutex_package is a string or not configured, don't generate recipe
            return None
    except ValueError as e:
        raise ValueError(f"Cannot generate mutex package recipe: {e}")

    # Create build string using distro name
    build_string = f"{distro.name}_{config['build_number']}"

    recipe = {
        "package": {"name": config["name"], "version": config["version"]},
        "build": {
            "number": config["build_number"],
            "string": build_string,
            "script": "",
        },
        "requirements": {
            "run_constraints": config["run_constraints"],
            "run_exports": {
                "weak": [
                    f"${{{{ pin_subpackage('{config['name']}', upper_bound='{config['upper_bound']}') }}}}"
                ]
            },
        },
        "about": {
            "homepage": f"https://github.com/robostack/ros-{distro.name}",
            "license": "BSD-3-Clause",
            "summary": f"The ROS2 distro mutex. To switch between ROS2 versions, you need to change the mutex.\nE.g. mamba install {config['name']}=*={distro.name} to switch to {distro.name}.",
        },
    }

    return recipe


def parse_package(pkg, distro, vinca_conf, path):
    name = pkg["name"].replace("_", "-")
    final_name = f"ros-{distro.name}-{name}"

    recipe = {
        "package": {"name": final_name, "version": pkg["version"]},
        "about": {
            "homepage": "https://www.ros.org/",
            "license": [str(lic) for lic in pkg["licenses"]],
            "summary": pkg["description"],
            "maintainers": [],
        },
        "extra": {"recipe-maintainers": ["robostack"]},
        "build": {
            "number": 0,
            "script": "${{ '$RECIPE_DIR/build_catkin.sh' if unix or wasm32 else '%RECIPE_DIR%\\\\bld_catkin.bat' }}",
        },
        "source": {},
        "requirements": {
            "build": [
                "${{ compiler('cxx') }}",
                "${{ compiler('c') }}",
                {
                    "if": "target_platform!='emscripten-wasm32'",
                    "then": ["${{ stdlib('c') }}"],
                },
                "ninja",
                "python",
                "patch",
                {"if": "unix", "then": ["make", "coreutils"]},
                "cmake",
                {"if": "build_platform != target_platform", "then": ["python"]},
                {
                    "if": "build_platform != target_platform",
                    "then": ["cross-python_${{ target_platform }}"],
                },
                {"if": "build_platform != target_platform", "then": ["cython"]},
                {"if": "build_platform != target_platform", "then": ["numpy"]},
                {"if": "build_platform != target_platform", "then": ["pybind11"]},
            ],
            "host": [],
            "run": [],
        },
    }

    if test := vinca_conf.get("_tests", {}).get(final_name):
        # parse as yaml
        text = test.read_text()
        test_content = ruamel.yaml.safe_load(text)
        recipe["test"] = test_content

    for p in pkg["authors"]:
        name = p.name + " (" + p.email + ")" if p.email else p.name
        recipe["about"]["maintainers"].append(name)

    for u in pkg["urls"]:
        # if u.type == 'repository' :
        #     recipe['source']['git'] = u.url
        #     recipe['source']['tag'] = recipe['package']['version']
        if u.type == "website":
            recipe["about"]["homepage"] = u.url

        # if u.type == 'bugtracker' :
        #    recipe['about']['url_issues'] = u.url

    if not recipe["source"].get("git", None):
        aux = path.split("/")
        print(aux[: len(aux) - 1])
        recipe["source"]["path"] = "/".join(aux[: len(aux) - 1])
        recipe["source"]["target_directory"] = f"{final_name}/src/work"

    for d in pkg["buildtool_depends"]:
        recipe["requirements"]["host"].extend(
            resolve_pkgname(d.name, vinca_conf, distro)
        )

    for d in pkg["build_depends"]:
        recipe["requirements"]["host"].extend(
            resolve_pkgname(d.name, vinca_conf, distro)
        )

    for d in pkg["build_export_depends"]:
        recipe["requirements"]["host"].extend(
            resolve_pkgname(d.name, vinca_conf, distro)
        )
        recipe["requirements"]["run"].extend(
            resolve_pkgname(d.name, vinca_conf, distro)
        )

    for d in pkg["buildtool_export_depends"]:
        recipe["requirements"]["host"].extend(
            resolve_pkgname(d.name, vinca_conf, distro)
        )
        recipe["requirements"]["run"].extend(
            resolve_pkgname(d.name, vinca_conf, distro)
        )

    for d in pkg["test_depends"]:
        recipe["requirements"]["host"].extend(
            resolve_pkgname(d.name, vinca_conf, distro)
        )

    for d in pkg["exec_depends"]:
        recipe["requirements"]["run"].extend(
            resolve_pkgname(d.name, vinca_conf, distro)
        )

    if pkg.get_build_type() in ["cmake", "catkin"]:
        recipe["build"]["script"] = (
            "${{ '$RECIPE_DIR/build_catkin.sh' if unix or wasm32 else '%RECIPE_DIR%\\\\bld_catkin.bat' }}"
        )

    return recipe


def main():
    global distro, unsatisfied_deps

    arguments = parse_command_line(sys.argv)

    base_dir = os.path.abspath(arguments.dir)
    vinca_yaml = os.path.join(base_dir, "vinca.yaml")
    vinca_conf = read_vinca_yaml(vinca_yaml)

    if arguments.trigger_new_versions:
        vinca_conf["trigger_new_versions"] = True
    else:
        vinca_conf["trigger_new_versions"] = vinca_conf.get(
            "trigger_new_versions", False
        )

    if arguments.package:
        pkg_files = glob.glob(arguments.package)

        python_version = None
        if "python_version" in vinca_conf:
            python_version = vinca_conf["python_version"]

        distro = Distro(
            vinca_conf["ros_distro"],
            python_version,
            vinca_conf["_snapshot"],
            vinca_conf["_additional_packages_snapshot"],
        )
        additional_pkgs, parsed_pkgs = [], []
        for f in pkg_files:
            parsed_pkg = catkin_pkg.package.parse_package(f)
            additional_pkgs.append(parsed_pkg.name)
            parsed_pkgs.append(parsed_pkg)

        distro.add_packages(additional_pkgs)

        outputs = []
        for f in pkg_files:
            pkg = catkin_pkg.package.parse_package(f)
            recipe = parse_package(pkg, distro, vinca_conf, f)

            if arguments.multiple_file:
                write_recipe_package(recipe)
            else:
                outputs.append(recipe)

        if not arguments.multiple_file:
            sources = {}
            for o in outputs:
                sources[o["package"]["name"]] = o["source"]
                del o["source"]
            write_recipe(sources, outputs, vinca_conf)

    else:
        if arguments.skip_already_built_repodata or vinca_conf.get("skip_existing"):
            skip_built_packages = set()
            fn = arguments.skip_already_built_repodata
            if not fn:
                fn = vinca_conf.get("skip_existing")

            yaml = ruamel.yaml.YAML()
            additional_recipe_names = set()
            for add_rec in glob.glob(
                os.path.join(base_dir, "additional_recipes", "**", "recipe.yaml")
            ):
                with open(add_rec) as fi:
                    add_rec_y = yaml.load(fi)
                if config.parsed_args.platform == "emscripten-wasm32":
                    additional_recipe_names.add(add_rec_y["package"]["name"])
                else:
                    if add_rec_y["package"]["name"] not in [
                        "ros-humble-rmw-wasm-cpp",
                        "ros-humble-wasm-cpp",
                        "ros-humble-dynmsg",
                        "ros-humble-test-wasm",
                    ]:
                        additional_recipe_names.add(add_rec_y["package"]["name"])

            print("Found additional recipes: ", additional_recipe_names)

            fns = list(fn)
            for fn in fns:
                selected_bn = None

                print(f"Fetching repodata: {fn}")
                repodata = get_repodata(fn, get_conda_subdir())
                # currently we don't check the build numbers of local repodatas,
                # only URLs
                if "://" in fn:
                    selected_bn = vinca_conf.get("build_number", 0)

                all_pkgs = repodata.get("packages", {})
                all_pkgs.update(repodata.get("packages.conda", {}))
                for _, pkg in all_pkgs.items():
                    is_built = False
                    if selected_bn is not None:
                        pkg_build_number = get_pkg_build_number(
                            selected_bn, pkg["name"], vinca_conf
                        )
                        if pkg["build_number"] == pkg_build_number:
                            is_built = True
                    else:
                        is_built = True

                    if is_built:
                        print(f"Skipping {pkg['name']}")
                        if vinca_conf["trigger_new_versions"]:
                            skip_built_packages.add((pkg["name"], pkg["version"]))
                        else:
                            skip_built_packages.add(pkg["name"])

                vinca_conf["skip_built_packages"] = skip_built_packages
        else:
            vinca_conf["skip_built_packages"] = []
        print("Skip built packages!", vinca_conf["skip_built_packages"])
        python_version = None
        if "python_version" in vinca_conf:
            python_version = vinca_conf["python_version"]

        distro = Distro(
            vinca_conf["ros_distro"],
            python_version,
            vinca_conf["_snapshot"],
            vinca_conf["_additional_packages_snapshot"],
        )

        selected_pkgs = get_selected_packages(distro, vinca_conf)

        vinca_conf["_selected_pkgs"] = selected_pkgs

        if arguments.source:
            source = generate_source_version(distro, vinca_conf)
            outputs = generate_outputs_version(distro, vinca_conf)
        else:
            source = generate_source(distro, vinca_conf)
            outputs = generate_outputs(distro, vinca_conf)

        if arguments.multiple_file:
            write_recipe(source, outputs, vinca_conf, False)
        else:
            write_recipe(source, outputs, vinca_conf)

        if unsatisfied_deps:
            print("Unsatisfied dependencies:", unsatisfied_deps)

    print("build scripts are created successfully.")
