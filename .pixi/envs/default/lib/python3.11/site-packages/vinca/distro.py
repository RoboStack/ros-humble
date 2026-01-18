import os
import urllib.request

from rosdistro import get_cached_distribution, get_index, get_index_url
from rosdistro.dependency_walker import DependencyWalker
from rosdistro.manifest_provider import get_release_tag


class Distro(object):
    def __init__(
        self,
        distro_name,
        python_version=None,
        snapshot=None,
        additional_packages_snapshot=None,
    ):
        index = get_index(get_index_url())
        self._distro = get_cached_distribution(index, distro_name)
        self.distro_name = distro_name
        self.snapshot = snapshot
        self.additional_packages_snapshot = additional_packages_snapshot

        # set up ROS environments
        if python_version is None:
            python_version = index.distributions[distro_name]["python_version"]
        os.environ["ROS_PYTHON_VERSION"] = "{0}".format(python_version)
        os.environ["ROS_DISTRO"] = "{0}".format(distro_name)
        if "ROS_ROOT" in os.environ:
            os.environ.pop("ROS_ROOT")
        if "ROS_PACKAGE_PATH" in os.environ:
            os.environ.pop("ROS_PACKAGE_PATH")
        self._walker = DependencyWalker(
            self._distro, evaluate_condition_context=os.environ
        )

        # cache distribution type
        self._distribution_type = index.distributions[distro_name]["distribution_type"]
        self._python_version = index.distributions[distro_name]["python_version"]
        self.build_packages = set()

        os.environ["ROS_VERSION"] = "1" if self.check_ros1() else "2"

    @property
    def name(self):
        return self.distro_name

    def add_packages(self, packages):
        self.build_packages = set(packages)

    def get_depends(self, pkg, ignore_pkgs=None):
        dependencies = set()

        if not self.check_package(pkg):
            print(f"{pkg} not in available packages anymore")
            return dependencies

        # if pkg comes from additional_packages_snapshot, extract from its package.xml
        if (
            self.additional_packages_snapshot
            and pkg in self.additional_packages_snapshot
        ):
            pkg_info = self.additional_packages_snapshot[pkg]
            xml_str = self.get_package_xml_for_additional_package(pkg_info)
            # parse XML
            import xml.etree.ElementTree as ET

            root = ET.fromstring(xml_str)
            # collect direct dependencies tags from package.xml
            dep_tags = [
                "depend",
                "build_depend",
                "buildtool_depend",
                "buildtool_export_depend",
                "exec_depend",
                "run_depend",
                "test_depend",
                "build_export_depend",
            ]
            direct = set()
            for tag in dep_tags:
                for elem in root.findall(f".//{tag}"):
                    if elem.text:
                        name = elem.text.strip()
                        direct.add(name)
            # add direct deps
            dependencies |= direct
            # recursively collect dependencies
            for dep in direct:
                if ignore_pkgs and dep in ignore_pkgs:
                    continue
                dependencies |= self.get_depends(dep, ignore_pkgs=ignore_pkgs)
            return dependencies

        # If the package is from upstream rosdistro, use the walker to get dependencies
        dependencies |= self._walker.get_recursive_depends(
            pkg,
            [
                "buildtool",
                "buildtool_export",
                "build",
                "build_export",
                "run",
                "test",
                "exec",
            ],
            ros_packages_only=True,
            ignore_pkgs=ignore_pkgs,
        )
        return dependencies

    def get_released_repo(self, pkg_name):
        if self.snapshot and pkg_name in self.snapshot:
            # In the case of snapshot, for rosdistro_additional_recipes
            # we also support a 'rev' field, so depending on what is available
            # we return either the tag or the rev, and the third argument is either 'rev' or 'tag'
            url = self.snapshot[pkg_name].get("url", None)
            if "tag" in self.snapshot[pkg_name].keys():
                tag_or_rev = self.snapshot[pkg_name].get("tag", None)
                ref_type = "tag"
            else:
                tag_or_rev = self.snapshot[pkg_name].get("rev", None)
                ref_type = "rev"

            return url, tag_or_rev, ref_type

        pkg = self._distro.release_packages[pkg_name]
        repo = self._distro.repositories[pkg.repository_name].release_repository
        release_tag = get_release_tag(repo, pkg_name)
        return repo.url, release_tag, "tag"

    def check_package(self, pkg_name):
        # If the package is in the additional_packages_snapshot, it is always considered valid
        # even if it is not in the released packages, as it is an additional
        # package specified in rosdistro_additional_recipes.yaml
        if (
            self.additional_packages_snapshot
            and pkg_name in self.additional_packages_snapshot
        ):
            return True
        # the .replace('_', '-') is needed for packages like 'hpp-fcl' that have hypen and not underscore
        # in the rosdistro metadata
        if (
            pkg_name in self._distro.release_packages
            or pkg_name.replace("_", "-") in self._distro.release_packages
        ):
            return self.snapshot is None or (
                pkg_name in self.snapshot or pkg_name.replace("_", "-") in self.snapshot
            )
        elif pkg_name in self.build_packages:
            return True
        else:
            return False

    def get_version(self, pkg_name):
        if self.snapshot and pkg_name in self.snapshot:
            return self.snapshot[pkg_name].get("version", None)

        pkg = self._distro.release_packages[pkg_name]
        repo = self._distro.repositories[pkg.repository_name].release_repository
        return repo.version.split("-")[0]

    def get_release_package_xml(self, pkg_name):
        if (
            self.additional_packages_snapshot
            and pkg_name in self.additional_packages_snapshot
        ):
            pkg_info = self.additional_packages_snapshot[pkg_name]
            return self.get_package_xml_for_additional_package(pkg_info)
        return self._distro.get_release_package_xml(pkg_name)

    def check_ros1(self):
        return self._distribution_type == "ros1"

    def get_python_version(self):
        return self._python_version

    def get_package_names(self):
        return self._distro.release_packages.keys()

    # Based on https://github.com/ros-infrastructure/rosdistro/blob/fad8d9f647631945847cb18bc1d1f43008d7a282/src/rosdistro/manifest_provider/github.py#L51C1-L69C29
    # But with the option to specify the name of the package.xml file in case the repo uses a non-standard name
    def get_package_xml_for_additional_package(self, pkg_info):
        # Build raw GitHub URL for package.xml
        raw_url_base = pkg_info.get("url")
        if raw_url_base.endswith(".git"):
            raw_url_base = raw_url_base[:-4]
        if "github.com" not in raw_url_base:
            raise RuntimeError(f"Cannot handle non-GitHub URL: {raw_url_base}")
        # Extract owner/repo
        owner_repo = raw_url_base.split("github.com/")[-1]
        # Use rev if available, otherwise fallback to tag
        ref = pkg_info.get("rev") or pkg_info.get("tag")
        xml_name = pkg_info.get("package_xml_name", "package.xml")
        additional_folder = pkg_info.get("additional_folder", "")
        if additional_folder != "":
            additional_folder = additional_folder + "/"
        raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{ref}/{additional_folder}{xml_name}"
        try:
            with urllib.request.urlopen(raw_url) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch package.xml from {raw_url}: {e}")
