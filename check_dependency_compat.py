#!/usr/bin/env python3
"""Detect incompatible dependency pins before (or after) building ROS packages.

Three modes, all platform-agnostic (default platform: the current machine):

1. ``solve`` (default): collect every non-ROS ``host``/``run`` dependency from the
   generated ``recipes/`` tree, add the ``mutex_package.run_constraints`` from
   ``vinca.yaml`` as hard requirements, write them into a single fake recipe and
   solve it with ``rattler-build --render-only --with-solve`` against the real
   ``conda_build_config.yaml``.  Nothing is built or downloaded except repodata.
   If the solve fails, the offending dependencies are removed iteratively so that
   *all* conflicts are reported, each with a focused explanation and the list of
   generated recipes that need it.

2. ``--migrations`` (on by default when conflicts are found): for every conflict,
   look up which conda-forge migration touches the pinned library and where the
   culprit's feedstock stands in that migration (done / in-pr / awaiting-parents …).
   This is the to-do list for conda-forge.

3. ``--stale``: inspect already-built artifacts (``output/<platform>/repodata.json``
   or a channel URL) and list ROS packages whose ``depends`` cannot be satisfied
   under the current mutex constraints / pins.  With ``--delete`` the local
   artifacts are removed (and the local index refreshed) so that a subsequent
   ``pixi run build`` (``--skip-existing``) rebuilds only those packages.  A
   ``pkg_additional_info.yaml`` build-number snippet is printed for the case where
   the stale builds are already on the channel.

Run inside the pixi environment, e.g. ``pixi run python check_dependency_compat.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform as _platform
import re
import shutil
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional
from urllib.request import urlopen

import ruamel.yaml

ROS_PREFIXES = ("ros-", "ros2-")
DEFAULT_CHANNELS = ["https://repo.prefix.dev/conda-forge"]
FAKE_PACKAGE_NAME = "robostack-dependency-compat-check"
DEFAULT_GLIBC = "2.17"  # fallback when c_stdlib_version is not in the variant config
DEFAULT_OSX = "15.0"
# "Platform: linux-64 [__unix=0=0, __linux=0=0, __glibc=0=0, ...]" -> a version of 0 means the
# virtual package is unknown for this (foreign) platform and every solve is meaningless.
_MISSING_VIRTUAL_RE = re.compile(r"Platform: \S+ \[[^\]]*?(__glibc|__osx|__cuda)=0=0")
_GLIBC_NEED_RE = re.compile(r"__glibc >=([0-9.]+)")
STATUS_CATEGORIES = (
    "done",
    "in-pr",
    "awaiting-pr",
    "awaiting-parents",
    "not-solvable",
    "bot-error",
)


# --------------------------------------------------------------------------- utils
def _yaml() -> ruamel.yaml.YAML:
    yaml = ruamel.yaml.YAML()
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return _yaml().load(stream) or {}


def detect_platform() -> str:
    machine = _platform.machine()
    if sys.platform.startswith("linux"):
        return "linux-aarch64" if machine == "aarch64" else "linux-64"
    if sys.platform == "darwin":
        return "osx-arm64" if machine == "arm64" else "osx-64"
    if sys.platform == "win32":
        return "win-64"
    raise RuntimeError(f"Cannot detect conda platform for {sys.platform}/{machine}")


def normalized(name: str) -> str:
    return name.lower().replace("_", "-")


def spec_name(spec: str) -> str:
    return spec.split()[0]


def is_ros_dependency(name: str) -> bool:
    return name.startswith(ROS_PREFIXES)


def channels_from_pixi(pixi_toml: Path) -> list[str]:
    """Take the channels of the ``build`` task so the check matches real builds."""
    try:
        with pixi_toml.open("rb") as stream:
            data = tomllib.load(stream)
        cmd = data["tasks"]["build"]["cmd"]
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return list(DEFAULT_CHANNELS)
    channels = re.findall(r"(?:^|\s)-c\s+(\S+)", cmd)
    return channels or list(DEFAULT_CHANNELS)


def platform_flags(platform: str) -> dict[str, Any]:
    """Selector namespace for the v0-style ``# [sel]`` comments in conda_build_config.yaml."""
    try:
        from vinca.v1_selectors import _platform_flags  # type: ignore

        flags: dict[str, Any] = dict(_platform_flags(platform))
    except ImportError:
        os_name, _, arch = platform.partition("-")
        flags = {
            "target_platform": platform,
            "linux": os_name == "linux",
            "osx": os_name == "osx",
            "win": os_name == "win",
            "unix": os_name in ("linux", "osx", "emscripten"),
            "emscripten": os_name == "emscripten",
            "wasm32": arch == "wasm32",
            "x86_64": arch == "64",
            "x86": arch == "64",
            "aarch64": arch in ("aarch64", "arm64"),
            "arm64": arch in ("aarch64", "arm64"),
            "ppc64le": arch == "ppc64le",
            "riscv64": arch == "riscv64",
        }
    flags.setdefault("win64", platform == "win-64")
    flags.setdefault("os", os)
    return flags


def eval_selector(selector: str, flags: dict[str, Any]) -> bool:
    try:
        from vinca.v1_selectors import _eval_condition  # type: ignore

        return bool(_eval_condition(selector, flags))
    except Exception:  # fall back to a plain python eval of the selector
        try:
            return bool(eval(selector, {"__builtins__": {}}, dict(flags)))  # noqa: S307
        except Exception:
            return False


# ----------------------------------------------------------------- requirements
def walk_requirements(
    value: Any, condition: Optional[str] = None
) -> Iterator[tuple[Optional[str], str]]:
    """Yield ``(condition, spec)`` for every requirement, keeping if/then/else."""
    if isinstance(value, str):
        yield condition, value.strip()
    elif isinstance(value, list):
        for item in value:
            yield from walk_requirements(item, condition)
    elif isinstance(value, dict):
        if "if" in value:
            cond = str(value["if"]).strip()
            then_cond = cond if condition is None else f"({condition}) and ({cond})"
            else_cond = f"not ({cond})" if condition is None else f"({condition}) and not ({cond})"
            yield from walk_requirements(value.get("then"), then_cond)
            if value.get("else") is not None:
                yield from walk_requirements(value.get("else"), else_cond)
        else:
            for item in value.values():
                yield from walk_requirements(item, condition)


def collect_requirements(
    recipes_dir: Path, sections: Iterable[str] = ("host", "run")
) -> dict[tuple[Optional[str], str], set[str]]:
    """Map ``(condition, spec)`` to the recipe names that require it."""
    yaml = _yaml()
    requirements: dict[tuple[Optional[str], str], set[str]] = defaultdict(set)
    for recipe_path in sorted(recipes_dir.glob("*/recipe.yaml")):
        with recipe_path.open(encoding="utf-8") as stream:
            recipe = yaml.load(stream) or {}
        name = recipe.get("package", {}).get("name", recipe_path.parent.name)
        reqs = recipe.get("requirements", {}) or {}
        for section in sections:
            for condition, spec in walk_requirements(reqs.get(section)):
                if not spec or "${{" in spec:
                    continue
                if is_ros_dependency(spec_name(spec)):
                    continue
                requirements[(condition, spec)].add(name)
    return requirements


def mutex_constraints(vinca_conf: dict[str, Any]) -> list[str]:
    mutex = vinca_conf.get("mutex_package")
    if isinstance(mutex, dict):
        return [str(item) for item in mutex.get("run_constraints", []) or []]
    return []


def write_fake_recipe(
    path: Path,
    pins: list[str],
    requirements: Iterable[tuple[Optional[str], str]],
    version: str = "0.0.0",
) -> None:
    grouped: dict[Optional[str], list[str]] = defaultdict(list)
    for condition, spec in requirements:
        if spec not in grouped[condition]:
            grouped[condition].append(spec)
    host: list[Any] = list(pins)
    host.extend(sorted(grouped.pop(None, [])))
    for condition in sorted(grouped, key=str):
        host.append({"if": condition, "then": sorted(grouped[condition])})
    recipe = {
        "package": {"name": FAKE_PACKAGE_NAME, "version": version},
        "build": {"number": 0, "script": ""},
        "requirements": {"build": [], "host": host, "run": []},
        "about": {
            "summary": "Synthetic package used to check that all RoboStack "
            "dependencies are co-installable under the current pins. Never built."
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        _yaml().dump(recipe, stream)


# ------------------------------------------------------------------------ solve
def glibc_floor(variant_config: Path, platform: str) -> str:
    """The glibc floor the packages are built for (``c_stdlib_version`` on linux)."""
    if os.environ.get("CONDA_OVERRIDE_GLIBC"):
        return os.environ["CONDA_OVERRIDE_GLIBC"]
    try:
        return variant_pins(variant_config, platform).get("c-stdlib-version", DEFAULT_GLIBC)
    except OSError:
        return DEFAULT_GLIBC


def rattler_build_executable() -> list[str]:
    exe = shutil.which("rattler-build")
    if exe:
        return [exe]
    if shutil.which("pixi"):
        return ["pixi", "run", "rattler-build"]
    raise SystemExit("rattler-build not found; run this script via `pixi run python ...`")


def run_solve(
    recipe: Path,
    variant_config: Path,
    channels: list[str],
    platform: str,
    output_dir: Path,
    *,
    verbose: bool = False,
) -> tuple[bool, str]:
    cmd = rattler_build_executable() + [
        "build",
        "--recipe",
        str(recipe),
        "-m",
        str(variant_config),
        "--render-only",
        "--with-solve",
        "--target-platform",
        platform,
        "--build-platform",
        platform,
        "--output-dir",
        str(output_dir),
        "--color",
        "never",
    ]
    for channel in channels:
        cmd += ["-c", channel]
    env = dict(os.environ, COLUMNS="500", NO_COLOR="1", RATTLER_BUILD_NO_SPINNER="1")
    # Solving for a foreign platform yields __glibc=0 / __osx=0 virtual packages, which
    # makes every package look uninstallable.  Provide sane defaults unless overridden.
    if platform.startswith("linux"):
        env.setdefault("CONDA_OVERRIDE_GLIBC", glibc_floor(variant_config, platform))
    elif platform.startswith("osx") and sys.platform != "darwin":
        env.setdefault("CONDA_OVERRIDE_OSX", DEFAULT_OSX)
    if verbose:
        print("  $", " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    text = proc.stdout + "\n" + proc.stderr
    failed = proc.returncode != 0 or "Cannot solve the request" in text
    return (not failed), text


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_TREE_RE = re.compile(r"^(?P<indent>[\s│]*)(?:├─|└─)\s+(?P<name>[A-Za-z0-9_.+-]+)")


def solver_block(text: str) -> str:
    """Return the final 'Cannot solve the request because of:' tree, cleaned."""
    text = _ANSI_RE.sub("", text)
    marker = "Cannot solve the request because of:"
    index = text.rfind(marker)
    if index == -1:
        return text.strip()
    return text[index:].strip()


def collapse_versions(text: str) -> str:
    """Collapse '7.6.0 | 7.6.0 | 7.6.0 ...' noise into '7.6.0 (x12)'."""

    def repl(match: re.Match[str]) -> str:
        items = [item.strip() for item in match.group(0).split("|")]
        return f"{items[0]} (x{len(items)})"

    return re.sub(r"(\S+)(?:\s*\|\s*\1)+", repl, text)


def parse_culprits(text: str, candidates: set[str], protected: set[str]) -> set[str]:
    """Names of directly requested (top-level) specs that the solver blames."""
    block = solver_block(text)
    lines = block.splitlines()
    entries: list[tuple[int, str]] = []
    for line in lines[1:]:
        match = _TREE_RE.match(line)
        if match:
            entries.append((len(match.group("indent")), match.group("name")))
    culprits: set[str] = set()
    if entries:
        # Top level of the tree = the requested specs the solver blames.
        min_indent = min(indent for indent, _ in entries)
        for indent, name in entries:
            if indent == min_indent and name in candidates and name not in protected:
                culprits.add(name)
    # The first line names one requested spec too ("because of: <name> ... cannot be
    # installed"), unless it is the generic "The following packages are incompatible".
    first = re.match(r"Cannot solve the request because of:\s*([A-Za-z0-9_.+-]+)", lines[0]) if lines else None
    if first and first.group(1) in candidates and first.group(1) not in protected:
        culprits.add(first.group(1))
    # "No candidates were found for <spec>" (spec does not exist at all on the channels).
    for match in re.finditer(r"No candidates were found for\s+([A-Za-z0-9_.+-]+)", block):
        if match.group(1) in candidates and match.group(1) not in protected:
            culprits.add(match.group(1))
    if not culprits:
        # Fallback: any requested dependency the solver mentions as uninstallable.
        for match in re.finditer(r"([A-Za-z0-9_.+-]+)\s+\S[^\n]*?cannot be installed", block):
            name = match.group(1)
            if name in candidates and name not in protected:
                culprits.add(name)
    return culprits


def pin_consistency(pins: list[str], variant: dict[str, str]) -> list[tuple[str, str]]:
    """Mutex run_constraints that contradict the rendered conda_build_config.yaml pins."""
    problems = []
    for spec in pins:
        parts = spec.split()
        if len(parts) < 2:
            continue
        pinned = variant.get(normalized(parts[0]))
        if pinned is not None and not constraint_compatible(parts[1], pinned):
            problems.append((spec, f"{parts[0]} {pinned}"))
    return problems


def _by_name(requirements: Iterable[tuple[Optional[str], str]]) -> dict[str, list[tuple[Optional[str], str]]]:
    grouped: dict[str, list[tuple[Optional[str], str]]] = defaultdict(list)
    for condition, spec in requirements:
        grouped[spec_name(spec)].append((condition, spec))
    return grouped


class Solver:
    """Thin wrapper that writes a fake recipe and solves it with rattler-build."""

    def __init__(self, args: argparse.Namespace, channels: list[str], workdir: Path) -> None:
        self.args = args
        self.channels = channels
        self.workdir = workdir
        self.calls = 0

    def solve(self, label: str, pins: list[str], requirements: Iterable[tuple[Optional[str], str]]) -> tuple[bool, str]:
        recipe = self.workdir / label / "recipe.yaml"
        write_fake_recipe(recipe, pins, requirements)
        self.calls += 1
        return run_solve(
            recipe,
            Path(self.args.variant_config),
            self.channels,
            self.args.platform,
            self.workdir / "output",
            verbose=self.args.verbose,
        )

    def find_partner(
        self,
        culprit: str,
        culprit_specs: list[tuple[Optional[str], str]],
        pins: list[str],
        others: dict[str, list[tuple[Optional[str], str]]],
    ) -> Optional[list[str]]:
        """Bisect the other dependencies down to the (few) names the culprit clashes with."""
        candidates = sorted(others)

        def fails(names: list[str]) -> bool:
            specs = list(culprit_specs)
            for name in names:
                specs.extend(others[name])
            ok, _ = self.solve(f"bisect-{culprit}", pins, specs)
            return not ok

        if not fails(candidates):
            return None
        while len(candidates) > 1:
            half = len(candidates) // 2
            first, second = candidates[:half], candidates[half:]
            if fails(first):
                candidates = first
            elif fails(second):
                candidates = second
            else:
                return candidates  # the clash needs members of both halves
        return candidates


def solve_mode(args: argparse.Namespace) -> int:
    recipes_dir = Path(args.recipes_dir)
    if not any(recipes_dir.glob("*/recipe.yaml")):
        raise SystemExit(
            f"No recipes found in {recipes_dir}; run `pixi run generate-recipes` first."
        )
    vinca_conf = load_yaml(Path(args.vinca))
    pins = mutex_constraints(vinca_conf) + list(args.pin)
    variant = variant_pins(Path(args.variant_config), args.platform)
    requirements = collect_requirements(recipes_dir)
    names = {spec_name(spec) for _, spec in requirements}
    channels = args.channel or channels_from_pixi(Path("pixi.toml"))
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    solver = Solver(args, channels, workdir)

    print(f"Platform:       {args.platform}")
    print(f"Channels:       {' '.join(channels)}")
    print(f"Variant config: {args.variant_config} ({len(variant)} single-valued pins)")
    print(f"Recipes:        {len(list(recipes_dir.glob('*/recipe.yaml')))} in {recipes_dir}")
    print(f"Dependencies:   {len(names)} distinct non-ROS packages, {len(requirements)} specs")
    print(f"Hard pins:      {', '.join(pins) if pins else '(none)'}")
    print()

    # 1. static check: mutex constraints vs. rendered conda_build_config.yaml
    pin_conflicts: dict[str, dict[str, Any]] = {}
    for spec, pinned in pin_consistency(pins, variant):
        print(f"PIN MISMATCH: mutex run_constraint '{spec}' vs {args.variant_config} '{pinned}'")
        pin_conflicts[spec_name(spec)] = {"mutex": spec, "variant": pinned, "explanation": "static"}
    if pin_conflicts:
        print("  -> align mutex_package.run_constraints in vinca.yaml with the rendered pins"
              " (or drop the migration from vinca_pinning.yaml).\n")

    # 2. iterative solve of the whole dependency set
    protected = {spec_name(spec) for spec in pins}
    active_pins = list(pins)
    excluded: dict[str, str] = {}
    active = dict(requirements)
    solved = False
    for iteration in range(1, args.max_iterations + 1):
        count = len({spec_name(s) for _, s in active})
        print(f"[{iteration}] solving {count} dependencies + {len(active_pins)} pins ...", flush=True)
        ok, text = solver.solve(FAKE_PACKAGE_NAME, active_pins, active.keys())
        if ok:
            solved = True
            break
        virtual = _MISSING_VIRTUAL_RE.search(_ANSI_RE.sub("", text))
        if virtual:
            print(f"\nThe solver lacks the virtual package {virtual.group(1)} for {args.platform}.")
            print("Set CONDA_OVERRIDE_GLIBC / CONDA_OVERRIDE_OSX / CONDA_OVERRIDE_CUDA and retry.\n")
            return 2
        blamed = parse_culprits(text, names | protected, set())
        removable = blamed - protected
        blamed_pins = blamed & protected
        if removable:
            for culprit in sorted(removable):
                print(f"    conflict: {culprit}")
                excluded[culprit] = text
                active = {key: value for key, value in active.items() if spec_name(key[1]) != culprit}
        elif blamed_pins:
            for name in sorted(blamed_pins):
                mutex_spec = next(s for s in active_pins if spec_name(s) == name)
                print(f"    pin conflict: {mutex_spec} (dropping it to continue)")
                pin_conflicts.setdefault(name, {"mutex": mutex_spec, "variant": variant.get(normalized(name))})
                pin_conflicts[name]["explanation"] = collapse_versions(solver_block(text))
                active_pins = [s for s in active_pins if spec_name(s) != name]
                protected.discard(name)
        else:
            print("\nSolver failed but no removable culprit could be identified:\n")
            print(collapse_versions(solver_block(text)))
            break
    else:
        print(f"Stopped after {args.max_iterations} iterations; raise --max-iterations.")

    print()
    if solved and not excluded and not pin_conflicts:
        print("OK: every dependency is co-installable under the current pins.")
        return 0

    report_conflicts(args, solver, excluded, pin_conflicts, requirements, active_pins, variant, solved)
    return 1


def report_conflicts(
    args: argparse.Namespace,
    solver: Solver,
    excluded: dict[str, str],
    pin_conflicts: dict[str, dict[str, Any]],
    requirements: dict[tuple[Optional[str], str], set[str]],
    pins: list[str],
    variant: dict[str, str],
    solved: bool,
) -> None:
    protected = {spec_name(spec) for spec in pins}
    if pin_conflicts:
        print(f"{len(pin_conflicts)} mutex constraint(s) contradict {args.variant_config}:")
        for name, info in pin_conflicts.items():
            if info.get("variant") is None:
                print(f"== {info['mutex']}  was blamed by the solver for {args.platform} (no rendered pin to compare):")
            else:
                print(f"== {info['mutex']}  vs  {info['variant']}")
            if info.get("explanation") not in (None, "static"):
                for line in info["explanation"].splitlines()[: args.max_lines]:
                    print("   | " + line)
        print()
    if solved:
        print(f"Dependencies solvable only after removing {len(excluded)} package(s):")
    else:
        print(f"Unsolvable; {len(excluded)} conflicting package(s) identified so far:")
    print()

    by_name = _by_name(requirements)
    details: dict[str, dict[str, Any]] = {}
    for culprit in sorted(excluded):
        specs = by_name[culprit]
        recipes = sorted(set().union(*(requirements[key] for key in specs)))
        ok, text = solver.solve(f"focus-{culprit}", pins, specs)
        partners: list[str] = []
        partner_specs: list[tuple[Optional[str], str]] = []
        if ok:
            others = {name: by_name[name] for name in by_name if name != culprit and name not in excluded}
            print(f"   {culprit}: installs alone; bisecting {len(others)} other dependencies for the clash ...", flush=True)
            partners = solver.find_partner(culprit, specs, pins, others) or []
            partner_specs = [spec for name in partners for spec in by_name[name]]
            ok, text = solver.solve(f"focus-{culprit}", pins, specs + partner_specs)
        block = collapse_versions(solver_block(text)) if not ok else (
            "(no clash reproducible in isolation; it only appears in the full set)"
        )
        # Precise attribution: which single mutex pin, when dropped, makes it solvable?
        blamed_pins: list[str] = []
        if not ok:
            for pin in pins:
                relaxed = [other for other in pins if other != pin]
                if solver.solve(f"attr-{culprit}", relaxed, specs + partner_specs)[0]:
                    blamed_pins.append(spec_name(pin))
            if not blamed_pins:  # several pins at once, or a pin-independent problem
                blamed_pins = sorted(
                    name for name in protected
                    if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(name)}\s", block)
                )
        blamed = sorted(set(blamed_pins) | set(partners))
        clash = [
            f"{name} (pinned {variant[normalized(name)]} by {args.variant_config})"
            if normalized(name) in variant and name not in protected
            else f"{name} (mutex run_constraint)" if name in protected
            else name
            for name in blamed
        ]
        details[culprit] = {
            "specs": [spec for _, spec in specs],
            "recipes": recipes,
            "pins": blamed,
            "partners": partners,
            "explanation": block,
        }
        print(f"== {culprit}  ({', '.join(spec for _, spec in specs)})")
        print(f"   needed by {len(recipes)} recipe(s): {', '.join(recipes[:8])}{' …' if len(recipes) > 8 else ''}")
        if clash:
            print(f"   clashes with: {'; '.join(clash)}")
        if any(len(spec.split()) > 1 for _, spec in specs):
            print("   note: the spec is version-restricted (dummy package in pkg_additional_info.yaml?);"
                  " a newer conda-forge version may already be built against the pinned libraries.")
        glibc_needs = sorted({m.group(1) for m in _GLIBC_NEED_RE.finditer(block)}, key=version_tuple)
        if glibc_needs and args.platform.startswith("linux"):
            floor = glibc_floor(Path(args.variant_config), args.platform)
            print(f"   note: needs glibc >= {glibc_needs[-1]} but the build floor (c_stdlib_version /"
                  f" CONDA_OVERRIDE_GLIBC) is {floor}; conda-forge is moving to a newer sysroot.")
        lines = block.splitlines()
        for line in lines[: args.max_lines]:
            print("   | " + line)
        if len(lines) > args.max_lines:
            print(f"   | … ({len(lines) - args.max_lines} more lines)")
        print()

    if args.json:
        Path(args.json).write_text(
            json.dumps({"pin_conflicts": pin_conflicts, "conflicts": details}, indent=2), encoding="utf-8"
        )
        print(f"Wrote {args.json}")
    print(f"({solver.calls} solver runs)")

    if args.migrations:
        report_migrations(details, pin_conflicts, pins, Path(args.pinning))


# ------------------------------------------------------------------- migrations
def _fetch_json(url: str) -> Optional[Any]:
    try:
        with urlopen(url, timeout=60) as response:  # noqa: S310
            return json.load(response)
    except Exception:
        return None


def report_migrations(
    details: dict[str, dict[str, Any]],
    pin_conflicts: dict[str, dict[str, Any]],
    pins: list[str],
    pinning_path: Path,
) -> None:
    try:
        from vinca.pinning import (  # type: ignore
            _migration_pin_keys,
            download_pinning_package,
            get_migration_status,
            package_feedstocks,
        )
    except ImportError:
        print("vinca is not importable; skipping conda-forge migration lookup.")
        return
    if not pinning_path.exists():
        print(f"{pinning_path} not found; skipping conda-forge migration lookup.")
        return
    spec = load_yaml(pinning_path)
    version = str(spec.get("conda_forge_pinning_version", ""))
    applied = {str(name).removesuffix(".yaml") for name in spec.get("migrations", []) or []}
    print(f"conda-forge migration status (conda-forge-pinning {version}):")
    try:
        _, payloads = download_pinning_package(version)
    except Exception as exc:
        print(f"  could not download conda-forge-pinning {version}: {exc}")
        return
    migration_keys = {name: _migration_pin_keys(payload) for name, payload in payloads.items()}
    status_cache: dict[str, Optional[dict[str, Any]]] = {}

    for name, info in pin_conflicts.items():
        if info.get("variant") is None:
            print(f"  mutex '{info['mutex']}' has no installable candidate together with the other pins and"
                  " dependencies (see explanation above); relax or drop the constraint, or fix the feedstock.")
            continue
        lib = normalized(name)
        setters = sorted(
            migration for migration, keys in migration_keys.items()
            if any(key == lib or key.startswith(lib + "-") for key in keys)
        )
        origin = ", ".join(
            f"{m} ({'applied' if m in applied else 'not applied'} in {pinning_path.name})" for m in setters
        ) or "the conda-forge-pinning base file"
        print(f"  mutex '{info['mutex']}' vs rendered pin '{info['variant']}' set by {origin}")
        print(f"    -> either update mutex_package.run_constraints in vinca.yaml to '{name} "
              f"{str(info['variant']).split()[-1]}.*' (mutex build-number bump), or remove the migration.")

    for culprit, info in details.items():
        libs = [normalized(name) for name in info["pins"]] or [normalized(spec_name(p)) for p in pins]
        relevant = sorted(
            name
            for name, keys in migration_keys.items()
            if any(key == lib or key.startswith(lib + "-") or key.startswith(lib + "_") for key in keys for lib in libs)
        )
        feedstocks = sorted(package_feedstocks(culprit))
        print(f"  {culprit}  (feedstock: {', '.join(feedstocks)}; pinned libs: {', '.join(libs)})")
        if not relevant:
            print(
                "    no active conda-forge migration touches these pins -> the feedstock's latest "
                "build is simply behind; it needs a rerender/rebuild or version bump on conda-forge."
            )
            for feedstock in feedstocks:
                print(f"    https://github.com/conda-forge/{feedstock}-feedstock")
            continue
        for migration in relevant:
            if migration not in status_cache:
                try:
                    status_cache[migration] = get_migration_status(migration)
                except Exception:
                    status_cache[migration] = None
            status = status_cache[migration]
            tag = "applied locally" if migration in applied else "NOT applied locally"
            if status is None:
                print(f"    {migration} [{tag}]: no status record on conda-forge")
                continue
            for feedstock in feedstocks:
                category = next(
                    (cat for cat in STATUS_CATEGORIES if feedstock in {normalized(n) for n in status.get(cat, [])}),
                    None,
                )
                pr_url = (status.get("_feedstock_status", {}).get(feedstock) or {}).get("pr_url", "")
                where = category or "not part of this migration"
                print(f"    {migration} [{tag}]: {feedstock} -> {where}  {pr_url}".rstrip())
    print()
    print("Legend: 'done' but still conflicting = the pin here is ahead of/behind conda-forge;")
    print("        'in-pr'/'awaiting-parents' = wait for or help land the conda-forge PR;")
    print("        no migration = open a rebuild/version-bump PR on the feedstock.")


# ----------------------------------------------------------------------- stale
_VERSION_PART_RE = re.compile(r"^(\d+)(.*)$")


def version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.strip().split("."):
        match = _VERSION_PART_RE.match(part)
        if not match:
            break
        parts.append(int(match.group(1)))
        if match.group(2):  # pre-release suffix such as '0a0': stop here
            break
    return tuple(parts)


def _pad(t: tuple[int, ...], n: int) -> tuple[int, ...]:
    return t + (0,) * (n - len(t))


def _cmp(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    n = max(len(a), len(b))
    a, b = _pad(a, n), _pad(b, n)
    return (a > b) - (a < b)


def pin_range(pin_version: str) -> tuple[tuple[int, ...], tuple[int, ...], bool]:
    """Return (lowest, upper_exclusive, exact) for a pin such as '1.90', '7.35.1.*' or '11.*'."""
    text = pin_version.strip()
    exact = not text.endswith(".*") and "*" not in text
    prefix = version_tuple(text.rstrip("*").rstrip("."))
    if not prefix:
        return (0,), (10**9,), False
    upper = prefix[:-1] + (prefix[-1] + 1,)
    return prefix, upper, exact


def constraint_compatible(constraint: str, pin_version: str) -> bool:
    """Whether some version can satisfy both the dependency constraint and the pin."""
    low, upper_excl, _ = pin_range(pin_version)
    constraint = constraint.strip()
    if constraint in ("", "*"):
        return True
    if "|" in constraint:
        return any(constraint_compatible(part, pin_version) for part in constraint.split("|"))
    for clause in [c.strip() for c in constraint.split(",") if c.strip()]:
        if clause.startswith(">="):
            if _cmp(upper_excl, version_tuple(clause[2:])) <= 0:
                return False
        elif clause.startswith(">"):
            if _cmp(upper_excl, version_tuple(clause[1:])) <= 0:
                return False
        elif clause.startswith("<="):
            if _cmp(low, version_tuple(clause[2:])) > 0:
                return False
        elif clause.startswith("<"):
            if _cmp(low, version_tuple(clause[1:])) >= 0:
                return False
        elif clause.startswith("!="):
            continue
        else:
            other = clause[2:] if clause.startswith("==") else clause
            other_low, other_upper, _ = pin_range(other)
            n = max(len(low), len(other_low))
            a, b = _pad(low, n), _pad(other_low, n)
            k = min(len(low), len(other_low))
            if a[:k] != b[:k]:
                return False
    return True


_CBC_KEY_RE = re.compile(r"^([A-Za-z0-9_.-]+):\s*(?:#\s*\[(.+?)\])?\s*$")
_CBC_ITEM_RE = re.compile(r"^\s+-\s*(?P<value>.*?)\s*(?:#\s*\[(?P<sel>.+?)\])?\s*$")


def variant_pins(variant_config: Path, platform: str) -> dict[str, str]:
    """Single-valued pins from conda_build_config.yaml for this platform, keyed by dep name.

    The file is scanned line by line (not YAML-loaded) so that values such as ``2.10``
    keep their exact spelling and the ``# [selector]`` comments stay attached.
    """
    flags = platform_flags(platform)
    pins: dict[str, str] = {}
    key: Optional[str] = None
    key_active = False
    chosen: list[str] = []

    def flush() -> None:
        if key and key_active and len(chosen) == 1:
            pins[normalized(key)] = chosen[0].split()[0]

    for raw in variant_config.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        key_match = _CBC_KEY_RE.match(line)
        if key_match:
            flush()
            key, key_selector = key_match.group(1), key_match.group(2)
            key_active = not key.startswith(("__", "zip_keys", "pin_run_as_build", "channel")) and (
                not key_selector or eval_selector(key_selector, flags)
            )
            chosen = []
            continue
        item_match = _CBC_ITEM_RE.match(line)
        if item_match and key_active:
            selector = item_match.group("sel")
            if selector and not eval_selector(selector, flags):
                continue
            value = item_match.group("value").strip().strip("'\"")
            if value and not value.startswith(("-", "[", "{")):
                chosen.append(value)
    flush()
    return pins


def load_repodata(source: str, platform: str) -> tuple[dict[str, Any], bool]:
    remote = "://" in source
    if remote:
        url = source.rstrip("/")
        if not url.endswith("repodata.json"):
            url = f"{url}/{platform}/repodata.json"
        with urlopen(url, timeout=300) as response:  # noqa: S310
            data = json.load(response)
    else:
        path = Path(source)
        if path.is_dir():
            path = path / "repodata.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    packages = dict(data.get("packages", {}))
    packages.update(data.get("packages.conda", {}))
    return packages, remote


def ros_name_map(vinca_conf: dict[str, Any]) -> dict[str, str]:
    """Map normalized conda suffix (e.g. 'cartographer-ros') to ROS names ('cartographer_ros')."""
    mapping: dict[str, str] = {}
    for key in ("rosdistro_snapshot", "rosdistro_additional_recipes"):
        path = vinca_conf.get(key)
        if path and Path(path).exists():
            for ros_name in load_yaml(Path(path)):
                mapping[normalized(str(ros_name))] = str(ros_name)
    return mapping


def stale_mode(args: argparse.Namespace) -> int:
    vinca_conf = load_yaml(Path(args.vinca))
    distro = vinca_conf.get("ros_distro", "")
    prefix = f"ros-{distro}-"
    pins: dict[str, str] = {}
    if not args.mutex_only:
        pins.update(variant_pins(Path(args.variant_config), args.platform))
    mutex_pins = {}
    for spec in mutex_constraints(vinca_conf) + list(args.pin):
        parts = spec.split()
        if len(parts) >= 2:
            mutex_pins[normalized(parts[0])] = parts[1]
    pins.update(mutex_pins)  # mutex constraints win
    mutex_name = (vinca_conf.get("mutex_package") or {}).get("name") if isinstance(
        vinca_conf.get("mutex_package"), dict) else None

    source = args.repodata or f"output/{args.platform}"
    packages, remote = load_repodata(source, args.platform)
    packages = {
        filename: record
        for filename, record in packages.items()
        if record.get("name", "").startswith(prefix) or record.get("name") == mutex_name
    }
    if not args.all_builds:
        # Only the newest build of every package matters for what users install now.
        newest: dict[str, int] = defaultdict(lambda: -1)
        for record in packages.values():
            newest[record["name"]] = max(newest[record["name"]], int(record.get("build_number", 0)))
        packages = {
            filename: record
            for filename, record in packages.items()
            if int(record.get("build_number", 0)) == newest[record["name"]]
        }
    scope = "all build numbers" if args.all_builds else "newest build of each package (see --all-builds)"
    print(f"Platform: {args.platform}   repodata: {source}   {distro} packages: {len(packages)} ({scope})")
    print(f"Pins checked: {', '.join(f'{k} {v}' for k, v in sorted(mutex_pins.items()))}")
    if not args.mutex_only:
        print(f"              + {len(pins) - len(mutex_pins)} single-valued pins from {args.variant_config}")
    print()

    stale: dict[str, list[tuple[str, str, str]]] = {}
    for filename, record in sorted(packages.items()):
        name = record.get("name", "")
        problems = []
        for dep in record.get("depends", []) + record.get("constrains", []):
            parts = dep.split()
            if len(parts) < 2:
                continue
            key = normalized(parts[0])
            pin = pins.get(key)
            if pin is None or is_ros_dependency(parts[0]):
                continue
            if not constraint_compatible(parts[1], pin):
                severity = "CONFLICT" if key in mutex_pins else "drift"
                problems.append((dep, f"{parts[0]} {pin}", severity))
        if problems:
            stale[filename] = problems

    if not stale:
        print("OK: no built package conflicts with the current pins.")
        return 0

    print(f"{len(stale)} stale artifact(s) whose dependencies conflict with the current pins")
    print("(CONFLICT = violates a mutex run_constraint, i.e. not installable next to the new mutex;")
    print(" drift    = built against an older conda_build_config.yaml pin, rebuild recommended):\n")
    by_dep: dict[str, int] = defaultdict(int)
    for filename, problems in stale.items():
        print(f"  {filename}")
        for dep, pin, severity in problems:
            print(f"      {severity:8s} has: {dep:45s} pin: {pin}")
            by_dep[pin] += 1
    print()
    print("Summary by pin: " + ", ".join(f"{pin} ({count})" for pin, count in sorted(by_dep.items())))
    print()

    names = sorted({packages[f]["name"] for f in stale})
    mapping = ros_name_map(vinca_conf)
    ros_names = []
    for name in names:
        if name == mutex_name:
            continue
        suffix = name[len(prefix):] if name.startswith(prefix) else name
        ros_names.append(mapping.get(normalized(suffix), suffix.replace("-", "_")))

    build_number = int(vinca_conf.get("build_number", 0)) + 1
    print("Rebuild only these packages")
    print("---------------------------")
    print("A) artifacts only exist locally: delete them (see --delete) and run `pixi run build`;")
    print("   --skip-existing then rebuilds exactly the missing packages.")
    print("B) artifacts are already on the channel: bump the build number of just these packages")
    print("   (and of the mutex, so its run_constraints are refreshed) and rebuild, then remove the")
    print("   old files from the channel.  pkg_additional_info.yaml snippet:\n")
    for ros_name in ros_names:
        print(f"{ros_name}:\n  build_number: {build_number}")
    if mutex_name:
        print(f"\n# vinca.yaml -> mutex_package:\n#   build_number: {build_number}")
    print()
    if remote:
        channel = source.split("://", 1)[1].split("/")[1] if "anaconda.org" in source else source
        print("Channel removal commands (anaconda.org):")
        for filename in stale:
            record = packages[filename]
            print(f"  anaconda remove {channel}/{record['name']}/{record['version']}/{args.platform}/{filename}")
        print()

    if args.delete:
        if remote:
            print("--delete only removes local artifacts; use the commands above for the channel.")
            return 1
        root = Path(source)
        root = root if root.is_dir() else root.parent
        removed = 0
        for filename in stale:
            target = root / filename
            if target.exists():
                target.unlink()
                removed += 1
                print(f"deleted {target}")
        print(f"\nDeleted {removed} artifact(s) from {root}.")
        index_root = root.parent
        rattler_index = shutil.which("rattler-index")
        if rattler_index:
            subprocess.run([rattler_index, "fs", str(index_root), "--force"], check=False)
            print(f"Re-indexed {index_root}.")
        else:
            print(f"Run `pixi run rattler-index fs {index_root} --force` to refresh the local index.")
        print("Now run `pixi run build` (skip-existing rebuilds only the deleted packages).")
    return 1


# ------------------------------------------------------------------------- main
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--platform", default=detect_platform(), help="conda platform (default: current machine)")
    parser.add_argument("--recipes-dir", default="recipes")
    parser.add_argument("--vinca", default="vinca.yaml")
    parser.add_argument("--variant-config", default="conda_build_config.yaml")
    parser.add_argument("--pinning", default="vinca_pinning.yaml", help="used for migration lookup")
    parser.add_argument("--channel", "-c", action="append", default=[], help="override channels (repeatable)")
    parser.add_argument("--pin", action="append", default=[], help="extra hard pin, e.g. 'libboost 1.90.*'")
    parser.add_argument("--workdir", default="output/compat_check", help="where fake recipes are written")
    parser.add_argument("--max-iterations", type=int, default=25)
    parser.add_argument("--max-lines", type=int, default=30, help="solver explanation lines per conflict")
    parser.add_argument("--json", help="write conflict details to this JSON file")
    parser.add_argument("--no-migrations", dest="migrations", action="store_false", help="skip conda-forge lookups")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--stale", action="store_true", help="check built artifacts instead of recipes")
    parser.add_argument("--repodata", help="repodata source for --stale: output/<platform>, a channel URL or repodata.json")
    parser.add_argument("--delete", action="store_true", help="with --stale: delete stale local artifacts")
    parser.add_argument(
        "--all-builds",
        action="store_true",
        help="with --stale: inspect every build number, not just the current vinca.yaml build_number",
    )
    parser.add_argument(
        "--mutex-only",
        action="store_true",
        help="with --stale: only check the mutex run_constraints, ignore conda_build_config.yaml drift",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stale:
        return stale_mode(args)
    return solve_mode(args)


if __name__ == "__main__":
    sys.exit(main())
