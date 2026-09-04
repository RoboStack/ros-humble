#!/usr/bin/env python3
"""
check_patches_clean_apply.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Scan *all* recipes inside the **recipes/** folder, keep only the parts
needed to verify that every declared *patch* still applies, and then
run **rattler-build** so the patch phase is executed – nothing else.

Usage
-----

    # From repository root
    python check_patches_clean_apply.py          # prepare + run
    python check_patches_clean_apply.py --dry    # prepare only
    python check_patches_clean_apply.py --dry --recipe ros-noetic-rviz
    python check_patches_clean_apply.py --clean  # delete output

The script creates (or refreshes) a sibling folder named
*recipes_only_patch*.  Every recipe that declares *patches:* gets a
**minimal** copy there; files referenced in *patches* are copied too.

Cross-platform patch coverage
------------------------------
``recipes/*/recipe.yaml`` only ever lists the patches vinca resolved
for the *host platform it was generated on* (see ``get_conda_subdir()``
in vinca) — a ``.win.patch`` or ``.osx.patch`` file never shows up
there when the recipes were rendered on Linux, so it would silently
never get exercised by this script. To catch that, the *patch/*
directory is rescanned directly (using the same ``<pkg>.<plat>.patch``
/ ``<pkg>.unix.patch`` / ``<pkg>.patch`` naming convention vinca uses)
and a **separate minimal recipe is generated per platform** that has a
distinct patch set for a given package (``linux``, ``osx``, ``win``,
``emscripten``, deduplicated when two platforms resolve to the same
patch list). This means every platform-specific patch on disk is
applied and checked regardless of which OS the script itself runs on.

Implementation details
----------------------

* Accepts both mapping or list forms of *source*.
* Strips out *requirements*, *test*, *outputs*… – only *package*,
  *source* and a stub *build* section remain.
* Automatically invokes ``rattler-build build`` if *--dry* is **not**
  given.

Modification summary
--------------------
* Each recipe is built individually (not batch)
* All outputs collected; failures reported with summary and details
* No early stopping; CI-friendly non-zero exit if any failures
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Union
import yaml

# Make console writes UTF-8 and never crash on unknown glyphs (Windows-safe)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

ROOT_DIR = Path.cwd()
RECIPES_DIR = ROOT_DIR / "recipes"
PATCH_RECIPES_DIR = ROOT_DIR / "recipes_only_patch"
PATCH_DIR = ROOT_DIR / "patch"

# Platform buckets vinca groups patch files into (see vinca.main.read_vinca_yaml).
PLATFORMS = ("linux", "osx", "win", "emscripten")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Check that patches apply cleanly.")
    ap.add_argument(
        "--dry",
        action="store_true",
        help="Only generate recipes_only_patch/, don't run rattler-build",
    )
    ap.add_argument(
        "--clean",
        action="store_true",
        help="Remove recipes_only_patch/ and exit",
    )
    ap.add_argument(
        "--recipe",
        action="append",
        default=[],
        metavar="RECIPE",
        help=(
            "Only check the specified recipe directory under recipes/. "
            "Repeat for multiple recipes, e.g. --recipe ros-humble-rviz2 "
            "--recipe ros-humble-tf2"
        ),
    )
    return ap.parse_args()


def find_recipe_files() -> List[Path]:
    return sorted(RECIPES_DIR.rglob("recipe.yaml"))


def resolve_requested_recipe_files(requested: List[str]) -> List[Path]:
    if not requested:
        return find_recipe_files()

    resolved: List[Path] = []
    missing: List[str] = []
    for name in requested:
        recipe_file = RECIPES_DIR / name / "recipe.yaml"
        if recipe_file.is_file():
            resolved.append(recipe_file)
        else:
            missing.append(name)

    if missing:
        print("The following requested recipe(s) were not found under recipes/:")
        for m in missing:
            print(f" - {m}")
        sys.exit(1)

    # Keep deterministic order and remove duplicates.
    return sorted(set(resolved))


def filter_sources(src: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if isinstance(src, dict):
        return [src] if "patches" in src else []
    elif isinstance(src, list):
        return [entry for entry in src if isinstance(entry, dict) and "patches" in entry]
    return []


def discover_all_patches(patch_dir: Path) -> Dict[str, Dict[str, List[Path]]]:
    """Group every ``patch/*.patch`` file by package name and platform bucket,
    mirroring vinca's own resolution logic (see ``read_vinca_yaml`` in
    vinca/main.py) but *without* filtering by the host platform — every
    bucket for every package is kept so platform-specific patches can be
    checked even when this script doesn't run on that platform."""
    patches: Dict[str, Dict[str, List[Path]]] = {}
    for x in sorted(patch_dir.glob("*.patch")):
        splitted = x.name.split(".")
        pkg_name = splitted[0]
        bucket = patches.setdefault(
            pkg_name, {"any": [], "osx": [], "linux": [], "win": [], "emscripten": []}
        )
        if len(splitted) == 3 and splitted[1] in ("osx", "linux", "win", "emscripten"):
            bucket[splitted[1]].append(x)
        elif len(splitted) == 3 and splitted[1] == "unix":
            bucket["linux"].append(x)
            bucket["osx"].append(x)
        else:
            bucket["any"].append(x)
    return patches


def platform_patch_variants(pkg_patches: Dict[str, List[Path]]) -> Dict[str, List[Path]]:
    """Return ``{platform: combined patch list}`` for every platform whose
    resolved patch set differs from one already seen (so identical sets,
    e.g. from a ``.unix.patch`` shared by linux+osx, are only tested once).
    Packages with no platform-specific patches at all get a single "any"
    entry instead of one per platform."""
    if not any(pkg_patches[p] for p in PLATFORMS):
        return {"any": list(pkg_patches["any"])} if pkg_patches["any"] else {}

    variants: Dict[str, List[Path]] = {}
    seen: Dict[tuple, str] = {}
    for plat in PLATFORMS:
        combined = pkg_patches["any"] + pkg_patches[plat]
        if not combined:
            continue
        key = tuple(combined)
        if key in seen:
            continue
        seen[key] = plat
        variants[plat] = combined
    return variants


def copy_and_ref_patch_files(patch_files: List[Path], dest_recipe_dir: Path) -> List[str]:
    """Copy patch files (from the repo-root patch/ dir) into the minimal
    recipe's own patch/ subfolder and return the recipe-relative paths to
    reference them by."""
    refs = []
    for p in patch_files:
        dest = dest_recipe_dir / "patch" / p.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        refs.append(f"patch/{p.name}")
    return refs


def write_minimal_recipe(
    dest_recipe_file: Path, pkg: Dict[str, Any], filtered_sources: List[Dict[str, Any]]
) -> None:
    minimal = {
        "package": pkg,
        "source": filtered_sources,
        "build": {"number": 0, "script": "echo patch-check"},
    }
    dest_recipe_file.parent.mkdir(parents=True, exist_ok=True)
    with dest_recipe_file.open("w", encoding="utf-8") as fh:
        yaml.dump(minimal, fh, sort_keys=False)


def prepare_patch_recipes(
    recipe_files: List[Path], all_patches: Dict[str, Dict[str, List[Path]]]
) -> List[Path]:
    recreated: List[Path] = []
    for recipe_file in recipe_files:
        with recipe_file.open("r", encoding="utf-8") as fh:
            recipe = yaml.safe_load(fh) or {}

        src_section = recipe.get("source")
        if src_section is None:
            continue

        pkg = recipe.get("package", {"name": recipe_file.parent.name, "version": "0"})
        pkg_name = pkg.get("name", recipe_file.parent.name)

        pkg_patches = all_patches.get(pkg_name)
        if pkg_patches is None:
            # No patch/*.patch file for this package on any platform -> skip
            continue

        variants = platform_patch_variants(pkg_patches)
        if not variants:
            continue

        entries = src_section if isinstance(src_section, list) else [src_section]
        dict_entries = [e for e in entries if isinstance(e, dict)]
        if not dict_entries:
            continue

        # Entries that the recipe.yaml already resolved patches onto (for
        # whichever host platform generated it) tell us where to attach our
        # freshly-discovered, platform-complete patch list. If none did
        # (e.g. the package has *only* a platform-specific patch that the
        # generating host never selected), fall back to the sole/first
        # source entry, which is the case for virtually every ROS package.
        already_patched = filter_sources(src_section)
        target_ids = {id(e) for e in already_patched} or {id(dict_entries[0])}

        rel_dir = recipe_file.parent.relative_to(RECIPES_DIR)
        for plat, patch_files in variants.items():
            dest_recipe_dir = PATCH_RECIPES_DIR / rel_dir / plat
            dest_recipe_file = dest_recipe_dir / "recipe.yaml"

            refs = copy_and_ref_patch_files(patch_files, dest_recipe_dir)
            variant_sources = []
            for entry in entries:
                if isinstance(entry, dict) and id(entry) in target_ids:
                    entry = dict(entry)
                    entry["patches"] = refs
                variant_sources.append(entry)

            patched_pkg = dict(pkg)
            patched_pkg["name"] = f"{patched_pkg['name']}-check-patches-{plat}"
            write_minimal_recipe(dest_recipe_file, patched_pkg, variant_sources)
            recreated.append(dest_recipe_file)

    return recreated


def run_rattler_build_individually(recipes: List[Path]) -> None:
    results = []
    for recipe_file in recipes:
        cmd = [
            "rattler-build",
            "build",
            "--recipe-dir",
            str(recipe_file.parent),
        ]
        print("\n Running:", " ".join(cmd), "\n", flush=True)
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, errors="replace", encoding="utf-8")
            # rattler-build's shared Git source cache can occasionally retain
            # tag refs whose objects were not fetched. Retry from a clean Git
            # cache rather than reporting a spurious patch failure.
            if proc.returncode != 0 and "Git error: Git fetch failed" in proc.stderr:
                shutil.rmtree(ROOT_DIR / "output" / "src_cache" / "git", ignore_errors=True)
                proc = subprocess.run(cmd, text=True, capture_output=True, errors="replace", encoding="utf-8")
            success = proc.returncode == 0
            results.append(
                {
                    "recipe": str(recipe_file.parent.relative_to(PATCH_RECIPES_DIR)),
                    "ok": success,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "rc": proc.returncode,
                }
            )
            print("   ->", "OK" if success else f"FAIL (rc={proc.returncode})", flush=True)
        except Exception as e:
            results.append(
                {
                    "recipe": str(recipe_file.parent.relative_to(PATCH_RECIPES_DIR)),
                    "ok": False,
                    "stdout": "",
                    "stderr": str(e),
                    "rc": -1,
                }
            )
            print("   -> EXCEPTION:", e, flush=True)

    # Summary
    failed = [r for r in results if not r["ok"]]
    print("\n================ Patch Application Summary ================\n")
    print(f"Total recipes tested: {len(results)}")
    print(f"Passed: {len(results) - len(failed)}")
    print(f"Failed: {len(failed)}")

    if not failed:
        print("\nAll patches applied cleanly.\n")
        return

    print("\n---------------- Failures (Summary) ----------------")
    for r in failed:
        print(f"- {r['recipe']} (rc={r['rc']})")

    print("\n---------------- Failures (Details) ----------------")
    for r in failed:
        print(f"\n### {r['recipe']} (rc={r['rc']})")
        if r["stdout"]:
            print("\n[stdout]")
            print(r["stdout"].rstrip())
        if r["stderr"]:
            print("\n[stderr]")
            print(r["stderr"].rstrip())
        print("\n----------------------------------------------------\n")

    sys.exit(2 if failed else 0)


def main() -> None:
    args = parse_args()

    if not RECIPES_DIR.is_dir():
        print("recipes/ folder not found – abort.")
        sys.exit(1)

    if not PATCH_DIR.is_dir():
        print("patch/ folder not found – abort.")
        sys.exit(1)

    if args.clean:
        shutil.rmtree(PATCH_RECIPES_DIR, ignore_errors=True)
        print(" Removed recipes_only_patch/")
        return

    if PATCH_RECIPES_DIR.exists():
        print("Refreshing recipes_only_patch/ …")
        shutil.rmtree(PATCH_RECIPES_DIR)

    recipe_files = resolve_requested_recipe_files(args.recipe)
    if args.recipe:
        print(f"Selected {len(recipe_files)} recipe(s) via --recipe.")

    all_patches = discover_all_patches(PATCH_DIR)
    recreated = prepare_patch_recipes(recipe_files, all_patches)
    if not recreated:
        print("No recipes with patches found – nothing to test.")
        return

    print(
        f"Prepared {len(recreated)} minimal recipe(s) in {PATCH_RECIPES_DIR}/ "
        f"(covering all of {PLATFORMS} regardless of the host platform)"
    )

    if not args.dry:
        run_rattler_build_individually(recreated)
    else:
        print("--dry given – rattler-build not executed.")


if __name__ == "__main__":
    main()
