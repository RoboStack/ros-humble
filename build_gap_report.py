#!/usr/bin/env python3
"""Report gaps between generated recipes and built conda artifacts.

Default behavior is platform-agnostic: it inspects all output/<platform> folders that
contain conda artifacts and reports gaps per platform. Only artifacts built with the
CURRENT build_number (and, for the mutex package, its own build_number) are counted —
older-build_number leftovers from a previous full rebuild are ignored, since counting
them makes the report claim far more packages are done than the current build actually
has.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Set

CONDA_SUFFIX = ".conda"
TARBZ2_SUFFIX = ".tar.bz2"

# Matches known conda platform directory names (osx-arm64, linux-64, win-64, …)
_PLATFORM_RE = re.compile(r'^(osx|linux|win|emscripten)-')

# Strips distro prefix so ros-jazzy-rclcpp, ros2-rclcpp, ros-kilted-rclcpp all
# normalise to "rclcpp" for cross-naming-style comparison.
# Handles two forms: ros-<word>-<base>  and  ros<digits>-<base>
_DISTRO_PREFIX_RE = re.compile(r'^(?:ros-[a-z]+-|ros\d+-)')

# check_patches_clean_apply.py builds throwaway "<pkg>-check-patches[-<platform>]"
# packages into this same output/<platform> folder to verify patches apply (the
# platform suffix was added later; older leftover artifacts may lack it). They
# never have a matching recipes/ directory and would otherwise show up as false
# "built but no recipe" gaps.
_CHECK_PATCHES_RE = re.compile(r'-check-patches(?:-(?:linux|osx|win|emscripten|any))?$')

_TOP_LEVEL_BUILD_NUMBER_RE = re.compile(r'^build_number:\s*(\d+)\s*$')
_MUTEX_HEADER_RE = re.compile(r'^mutex_package:\s*$')
_MUTEX_NAME_RE = re.compile(r'^\s+name:\s*"?([\w.-]+)"?\s*$')
_MUTEX_BUILD_NUMBER_RE = re.compile(r'^\s+build_number:\s*(\d+)\s*$')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare recipe directories with built package artifacts and report gaps. "
            "By default, checks every platform folder found under output/."
        )
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output root directory containing platform subfolders (default: output)",
    )
    parser.add_argument(
        "--recipes-dir",
        default="recipes",
        help="Recipes directory (default: recipes)",
    )
    parser.add_argument(
        "--platform",
        action="append",
        default=[],
        help=(
            "Platform folder to inspect (repeatable). "
            "If omitted, all detected platform folders are inspected."
        ),
    )
    parser.add_argument(
        "--vinca-yaml",
        default="vinca.yaml",
        help="vinca.yaml to read the current build_number/mutex from (default: vinca.yaml)",
    )
    parser.add_argument(
        "--build-number",
        type=int,
        default=None,
        help="Override the build_number to filter artifacts by (default: parsed from --vinca-yaml)",
    )
    parser.add_argument(
        "--any-build-number",
        action="store_true",
        help="Don't filter by build_number at all (count every artifact regardless of age)",
    )
    parser.add_argument(
        "--pkg-additional-info",
        default="pkg_additional_info.yaml",
        help=(
            "pkg_additional_info.yaml to read per-package build_number overrides from "
            "(default: pkg_additional_info.yaml)"
        ),
    )
    return parser.parse_args()


def normalize_name(name: str) -> str:
    """Strip ros-<distro>- / ros2- prefix for cross-naming-style comparison."""
    return _DISTRO_PREFIX_RE.sub("", name)


def is_conda_artifact(filename: str) -> bool:
    return filename.endswith(CONDA_SUFFIX) or filename.endswith(TARBZ2_SUFFIX)


def package_name_from_artifact(filename: str) -> str | None:
    stem = filename
    if stem.endswith(CONDA_SUFFIX):
        stem = stem[: -len(CONDA_SUFFIX)]
    elif stem.endswith(TARBZ2_SUFFIX):
        stem = stem[: -len(TARBZ2_SUFFIX)]
    else:
        return None

    parts = stem.rsplit("-", 2)
    if len(parts) != 3:
        return None
    name = parts[0]
    if _CHECK_PATCHES_RE.search(name):
        return None
    return name


def build_number_from_artifact(filename: str) -> int | None:
    """Extract the trailing _<N> build number from a conda artifact's build string."""
    stem = filename
    if stem.endswith(CONDA_SUFFIX):
        stem = stem[: -len(CONDA_SUFFIX)]
    elif stem.endswith(TARBZ2_SUFFIX):
        stem = stem[: -len(TARBZ2_SUFFIX)]
    else:
        return None

    parts = stem.rsplit("-", 2)
    if len(parts) != 3:
        return None
    build_string = parts[2]
    suffix = build_string.rsplit("_", 1)[-1]
    return int(suffix) if suffix.isdigit() else None


def read_vinca_config(vinca_yaml: Path) -> tuple[int | None, str | None, int | None]:
    """Parse (build_number, mutex_package_name, mutex_build_number) out of vinca.yaml
    without requiring a YAML library, since this script has no other dependencies."""
    if not vinca_yaml.is_file():
        return None, None, None

    build_number: int | None = None
    mutex_name: str | None = None
    mutex_build_number: int | None = None
    in_mutex_block = False

    for line in vinca_yaml.read_text().splitlines():
        if in_mutex_block:
            if line.startswith((" ", "\t")):
                m = _MUTEX_NAME_RE.match(line)
                if m:
                    mutex_name = m.group(1)
                m = _MUTEX_BUILD_NUMBER_RE.match(line)
                if m:
                    mutex_build_number = int(m.group(1))
                continue
            in_mutex_block = False  # fall through: this line starts the next top-level key

        m = _TOP_LEVEL_BUILD_NUMBER_RE.match(line)
        if m:
            build_number = int(m.group(1))
            continue
        if _MUTEX_HEADER_RE.match(line):
            in_mutex_block = True

    return build_number, mutex_name, mutex_build_number


_PKG_INFO_TOP_LEVEL_KEY_RE = re.compile(r'^([A-Za-z0-9_.]+):\s*(?:#.*)?$')
_PKG_INFO_BUILD_NUMBER_RE = re.compile(r'^\s+build_number:\s*(\d+)\s*$')


def read_pkg_build_number_overrides(pkg_info_yaml: Path) -> dict[str, int]:
    """Parse per-package `build_number:` overrides out of pkg_additional_info.yaml —
    a surgical way to force a rebuild of just one package without bumping vinca.yaml's
    global build_number for everything. Keyed by the ROS package name as written there
    (underscores), same convention as normalize_name(...).replace('-', '_')."""
    overrides: dict[str, int] = {}
    if not pkg_info_yaml.is_file():
        return overrides

    current_key: str | None = None
    for line in pkg_info_yaml.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            m = _PKG_INFO_TOP_LEVEL_KEY_RE.match(line)
            current_key = m.group(1) if m else None
            continue
        if current_key is None:
            continue
        m = _PKG_INFO_BUILD_NUMBER_RE.match(line)
        if m:
            overrides[current_key] = int(m.group(1))

    return overrides


def expected_build_number(
    norm_name: str,
    build_number: int | None,
    mutex_norm_name: str | None,
    mutex_build_number: int | None,
    pkg_build_number_overrides: dict[str, int],
) -> int | None:
    """The build_number a package's artifact must carry to count as "current":
    the mutex's own build_number for the mutex package, a per-package override from
    pkg_additional_info.yaml if one exists for it, otherwise the global build_number."""
    if mutex_norm_name is not None and norm_name == mutex_norm_name and mutex_build_number is not None:
        return mutex_build_number
    override = pkg_build_number_overrides.get(norm_name.replace("-", "_"))
    if override is not None:
        return override
    return build_number


def discover_platform_dirs(output_root: Path) -> list[str]:
    platforms: list[str] = []
    if not output_root.exists():
        return platforms

    for child in sorted(output_root.iterdir()):
        if not child.is_dir():
            continue
        if not _PLATFORM_RE.match(child.name):
            continue
        try:
            has_artifact = any(
                entry.is_file() and is_conda_artifact(entry.name)
                for entry in child.iterdir()
            )
        except PermissionError:
            continue
        if has_artifact:
            platforms.append(child.name)

    return platforms


def built_packages_for_platform(
    output_root: Path,
    platform: str,
    build_number: int | None,
    mutex_norm_name: str | None,
    mutex_build_number: int | None,
    pkg_build_number_overrides: dict[str, int],
) -> Set[str]:
    platform_dir = output_root / platform
    packages: Set[str] = set()
    if not platform_dir.exists() or not platform_dir.is_dir():
        return packages

    for artifact in platform_dir.iterdir():
        if not artifact.is_file() or not is_conda_artifact(artifact.name):
            continue
        package_name = package_name_from_artifact(artifact.name)
        if not package_name:
            continue
        norm_name = normalize_name(package_name)

        if build_number is not None:
            artifact_build_number = build_number_from_artifact(artifact.name)
            expected = expected_build_number(
                norm_name, build_number, mutex_norm_name, mutex_build_number, pkg_build_number_overrides
            )
            if artifact_build_number != expected:
                continue

        packages.add(norm_name)

    return packages


def recipe_directories(recipes_dir: Path) -> Set[str]:
    if not recipes_dir.exists():
        return set()
    return {entry.name for entry in recipes_dir.iterdir() if entry.is_dir()}


def print_list(title: str, values: Iterable[str]) -> None:
    values = sorted(values)
    print(f"{title}: {len(values)}")
    if values:
        for value in values:
            print(f"  - {value}")


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_dir)
    recipes_dir = Path(args.recipes_dir)

    recipes = recipe_directories(recipes_dir)
    if not recipes:
        print(f"No recipe directories found in: {recipes_dir}")
        return 1

    selected_platforms = args.platform or discover_platform_dirs(output_root)
    if not selected_platforms:
        print(
            "No platform artifact folders found under "
            f"{output_root} (expected e.g. output/osx-arm64, output/linux-64)."
        )
        return 1

    if args.any_build_number:
        build_number, mutex_name, mutex_build_number = None, None, None
        pkg_build_number_overrides: dict[str, int] = {}
    else:
        build_number, mutex_name, mutex_build_number = read_vinca_config(Path(args.vinca_yaml))
        if args.build_number is not None:
            build_number = args.build_number
        if build_number is None:
            print(
                f"Warning: could not read build_number from {args.vinca_yaml} "
                "(pass --build-number or --any-build-number) — counting artifacts "
                "from every build_number, including stale ones from earlier rebuilds.\n"
            )
        pkg_build_number_overrides = read_pkg_build_number_overrides(Path(args.pkg_additional_info))
    mutex_norm_name = normalize_name(mutex_name) if mutex_name else None

    if build_number is not None:
        mutex_note = (
            f", mutex build_number {mutex_build_number}" if mutex_build_number is not None else ""
        )
        override_note = (
            f", {len(pkg_build_number_overrides)} per-package override(s) from {args.pkg_additional_info}"
            if pkg_build_number_overrides
            else ""
        )
        print(f"Filtering to build_number {build_number}{mutex_note}{override_note}\n")

    for idx, platform in enumerate(selected_platforms):
        built = built_packages_for_platform(
            output_root, platform, build_number, mutex_norm_name, mutex_build_number, pkg_build_number_overrides
        )

        # Normalize recipe names for comparison so ros-jazzy-X and ros2-X match.
        # Iterate in sorted (not set-hash) order so the displayed name for a
        # dual-named package is deterministic across runs, not whichever of the
        # two happens to come last per Python's randomized set iteration order —
        # "ros2-X" sorts after "ros-<distro>-X" (- < digit in ASCII) so the
        # shared ros2- convention consistently wins when both exist.
        norm_to_recipe: dict[str, str] = {normalize_name(r): r for r in sorted(recipes)}
        norm_recipes = set(norm_to_recipe)

        print(f"Platform: {platform}")
        extra_norm = built - norm_recipes
        extra_display = sorted(extra_norm)
        print(f"Built package artifacts without matching recipe directory: {len(extra_display)}")
        for name in extra_display:
            print(f"  - {name}")
        print()
        missing_norm = norm_recipes - built
        missing_display = sorted(norm_to_recipe[n] for n in missing_norm)
        print(
            f"Recipe directories without built artifact on {platform} platform: "
            f"{len(missing_display)} out of {len(norm_recipes)}"
        )
        if missing_display:
            for recipe in missing_display:
                print(f"  - {recipe}")

        if idx != len(selected_platforms) - 1:
            print("\n" + "-" * 72 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
