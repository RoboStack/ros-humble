import yaml
import sys
import os
import argparse
import re
import networkx as nx
import subprocess
import shutil
import ruamel.yaml
from .utils import get_repodata
from vinca import config
from vinca.distro import Distro
from distutils.dir_util import copy_tree

distro_version = None
ros_prefix = None

# arches = ["linux-64", "linux-aarch64", "win-64", "osx-64", "osx-arm64"]
# arch_to_fname = {
#     "linux-64": "linux",
#     "linux-aarch64": "linux_aarch_64",
#     "win-64": "win",
#     "osx-64": "osx",
#     "osx-arm64": "osx_arm64"
# }


def to_ros_name(distro, pkg_name):
    shortname = pkg_name[len(ros_prefix) + 1 :]
    if distro.check_package(shortname):
        return shortname
    elif distro.check_package(shortname.replace("-", "_")):
        return shortname.replace("-", "_")
    else:
        raise RuntimeError(f"Couldnt convert {pkg_name} to ROS pkg name")


def create_migration_instructions(arch, packages_to_migrate, trigger_branch):
    url = "https://conda.anaconda.org/robostack/"

    yaml = ruamel.yaml.YAML()
    with open("vinca.yaml", "r") as fi:
        vinca_conf = yaml.load(fi)

    global distro_version, ros_prefix
    distro_version = vinca_conf["ros_distro"]
    ros_prefix = f"ros-{distro_version}"

    repodata = get_repodata(url, arch)

    packages = repodata["packages"]
    to_migrate = set()
    ros_pkgs = set()
    for pkey in packages:
        if not pkey.startswith(ros_prefix):
            continue

        pname = pkey.rsplit("-", 2)[0]
        ros_pkgs.add(pname)

        p = packages[pkey]

        for d in p.get("depends", []):
            if d.split()[0] in packages_to_migrate:
                # print(f"need to migrate {pkey}")
                to_migrate.add(pname)

    latest = {}
    for pkg in ros_pkgs:
        current = current_version = None
        for pkey in packages:
            if packages[pkey]["name"] == pkg:
                tmp = packages[pkey]["version"].split(".")
                version = []
                for el in tmp:
                    if el.isdecimal():
                        version.append(int(el))
                    else:
                        x = re.search(r"[^0-9]", version).start()
                        version.append(int(el[:x]))

                version = tuple(version)

                if not current or version > current_version:
                    current_version = version
                    current = pkey
        latest[pkg] = current

    # now we can build the graph ...

    G = nx.DiGraph()
    for pkg, pkgkey in latest.items():
        full_pkg = packages[pkgkey]
        for dep in full_pkg.get("depends", []):
            req = dep.split(" ")[0]
            G.add_node(pkg)
            if req.startswith(ros_prefix):
                G.add_edge(pkg, req)

    gsorted = nx.topological_sort(G)
    gsorted = list(reversed([g for g in gsorted]))

    to_migrate = sorted(to_migrate, key=lambda x: gsorted.index(x))

    print("Sorted to migrate: ", to_migrate)

    distro = Distro(distro_version)
    # import IPython; IPython.embed()

    ros_names = []
    for pkg in to_migrate:
        ros_names.append(to_ros_name(distro, pkg))
    print("Final names: ", ros_names)

    vinca_conf["packages_select_by_deps"] = ros_names
    vinca_conf["is_migration"] = True
    vinca_conf["skip_existing"] = []

    with open("vinca.yaml", "w") as fo:
        yaml.dump(vinca_conf, fo)

    if os.path.exists("recipes"):
        shutil.rmtree("recipes")

    mutex_path = os.path.join(
        config.parsed_args.dir, "additional_recipes/ros-distro-mutex"
    )
    if os.path.exists(mutex_path):
        goal_folder = os.path.join(
            config.parsed_args.dir, "recipes", "ros-distro-mutex"
        )
        os.makedirs(goal_folder, exist_ok=True)
        copy_tree(mutex_path, goal_folder)

    subprocess.check_call(
        ["vinca", "-d", config.parsed_args.dir, "--multiple", "--platform", arch]
    )

    # TODO remove hard coded build branch here!
    recipe_dir = os.path.join(config.parsed_args.dir, "recipes")
    subprocess.check_call(
        [
            "vinca-azure",
            "--platform",
            arch,
            "--trigger-branch",
            "buildbranch_linux",
            "-d",
            recipe_dir,
            "--additional-recipes",
        ]
    )


def parse_command_line(argv):
    parser = argparse.ArgumentParser(
        description="Conda recipe Azure pipeline generator for ROS packages"
    )

    default_dir = "./recipes"
    parser.add_argument(
        "-d",
        "--dir",
        dest="dir",
        default=default_dir,
        help="The recipes directory to process (default: {}).".format(default_dir),
    )

    parser.add_argument(
        "-t", "--trigger-branch", dest="trigger_branch", help="Trigger branch for Azure"
    )

    parser.add_argument(
        "-p",
        "--platform",
        dest="platform",
        default="linux-64",
        help="Platform to emit build pipeline for",
    )

    parser.add_argument(
        "-a",
        "--additional-recipes",
        action="store_true",
        help="search for additional_recipes folder?",
    )

    arguments = parser.parse_args(argv[1:])
    config.parsed_args = arguments
    return arguments


def main():
    args = parse_command_line(sys.argv)

    mfile = os.path.join(args.dir + "/migration.yaml")
    with open(mfile, "r") as fi:
        migration = yaml.safe_load(fi)
        print(migration)
        create_migration_instructions(
            args.platform, migration.get("packages", []), args.trigger_branch
        )
