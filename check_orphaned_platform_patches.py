#!/usr/bin/env python3
"""
check_orphaned_platform_patches.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Detect patch files in ``patch/`` that vinca will silently never wire
into any recipe's ``patches:`` list.

Background
----------
vinca (see ``vinca/main.py`` around the ``patch_dir`` glob, and
``vinca/utils.py::add_package_name_variants``) builds a dict keyed by
the patch filename's prefix (everything before an optional
``.osx``/``.win``/``.linux``/``.unix``/``.emscripten`` suffix), then
cross-links name-prefix variants of the *same* logical package
(``X`` <-> ``ros-X`` <-> ``ros2-X`` <-> ``ros-<distro>-X``) via
``dict.setdefault()``.

``setdefault`` only fills in a key that is still *absent*. If a
package has a plain patch under one prefix (say ``ros2-foo.patch``)
and a platform-specific patch under a *different* prefix (say
``ros-jazzy-foo.osx.patch``), both prefixes already exist as their own
dict entries by the time the cross-link step runs, so the two never
merge. Whichever prefix vinca does *not* resolve as the package's
final conda name for a given recipe simply never appears in that
recipe's ``patches:`` list -- with no error and no warning. This
exact bug orphaned ``ros-jazzy-sick-scan-xd.osx.patch`` for months
before it was renamed to ``ros2-sick-scan-xd.osx.patch`` (matching the
prefix jazzy actually resolves sick_scan_xd's own patch under).

``check_patches_clean_apply.py`` does not catch this: it verifies that
every patch file on disk applies cleanly to source, but never checks
whether vinca's real name-resolution would actually attach that file
to any package's generated recipe at all.

What this script does
----------------------
Replicates vinca's exact patch-dict-construction and
``add_package_name_variants`` shortname-stripping logic (kept in sync
with whatever revision this repo's ``pixi.toml`` pins vinca to -- if
that mechanism ever changes upstream, re-check this script). It groups
patch-file prefixes by their computed "shortname" and flags any group
where more than one *distinct* literal prefix was actually used by a
file on disk: only one of those prefixes can ever be the resolved
package name for a given recipe, so content under the others is dead.

Exit code is non-zero (and the offending groups are printed) if any
such collision is found.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PATCH_DIR = REPO_ROOT / "patch"

_ROS_DISTRO_RE = re.compile(r"^ros_distro:\s*(\S+)\s*$", re.MULTILINE)


def get_ros_distro() -> str:
    vinca_yaml = (REPO_ROOT / "vinca.yaml").read_text()
    match = _ROS_DISTRO_RE.search(vinca_yaml)
    if not match:
        print("Could not find 'ros_distro:' in vinca.yaml", file=sys.stderr)
        sys.exit(2)
    return match.group(1)


def build_patches_dict(patch_dir: Path) -> dict[str, dict[str, list[str]]]:
    """Mirrors the glob loop in vinca/main.py that builds vinca_conf['_patches']."""
    patches: dict[str, dict[str, list[str]]] = {}
    for x in sorted(glob.glob(os.path.join(str(patch_dir), "*.patch"))):
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
    return patches


def shortname_of(name: str, ros_distro: str) -> str:
    """Mirrors the prefix-stripping in vinca/utils.py::add_package_name_variants."""
    legacy_prefix = f"ros-{ros_distro}-"
    if name.startswith(legacy_prefix):
        return name[len(legacy_prefix):]
    elif name.startswith("ros2-"):
        return name[len("ros2-"):]
    elif name.startswith("ros-"):
        return name[len("ros-"):]
    else:
        return name


def main() -> int:
    ros_distro = get_ros_distro()
    patches = build_patches_dict(PATCH_DIR)

    groups: dict[str, list[str]] = {}
    for prefix in patches:
        groups.setdefault(shortname_of(prefix, ros_distro), []).append(prefix)

    collisions = {
        shortname: prefixes
        for shortname, prefixes in groups.items()
        if len(prefixes) > 1
    }

    if not collisions:
        print(f"OK: no orphaned platform-specific patches ({len(patches)} patch-file prefixes scanned).")
        return 0

    print(
        "ORPHANED PLATFORM PATCH RISK: the following packages have patch files "
        "spread across more than one name-prefix variant. vinca's "
        "add_package_name_variants() cross-links prefix variants via "
        "dict.setdefault(), which is a no-op once a variant already exists as its "
        "own entry -- so only ONE of the prefixes below will end up attached to "
        "the package's real generated recipe; any platform-specific patch under "
        "the others is silently never applied.\n",
        file=sys.stderr,
    )
    for shortname, prefixes in sorted(collisions.items()):
        print(f"  {shortname}:", file=sys.stderr)
        for prefix in sorted(prefixes):
            files = [
                os.path.basename(f)
                for platform_files in patches[prefix].values()
                for f in platform_files
            ]
            print(f"    {prefix}: {', '.join(sorted(files))}", file=sys.stderr)
    print(
        "\nFix: rename the patch file(s) so every file for a given package shares "
        "the SAME name prefix (matching whichever prefix that package's own "
        "recipe.yaml actually resolves to -- check recipes/<pkg>/*/recipe.yaml's "
        "source.patches entries, or regenerate recipes locally and inspect).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
