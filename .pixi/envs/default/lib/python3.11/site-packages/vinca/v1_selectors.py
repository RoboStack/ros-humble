"""
Evaluate rattler-build v1-style selectors (``if`` / ``then`` / optional ``else``)
inside YAML files already loaded with ``ruamel.yaml``, following the style documented
in the rattler-build documentation at https://rattler.build/latest/selectors/ .
One major difference is that build_platform variable is not supported.

Usage
-----
>>> from v1_selectors import evaluate_selectors
>>> data = yaml.load(open("recipe.yaml"))
>>> clean = evaluate_selectors(data, target_platform="linux-64")
"""

from __future__ import annotations

import copy
from typing import Any, Mapping, MutableMapping, Sequence

import jinja2


# -----------------------------------------------------------------------------#
# Helper – platform → selector variables                                       #
# -----------------------------------------------------------------------------#
def _platform_flags(platform: str | None) -> dict[str, bool | str]:
    """Return the boolean/os/arch flags defined by rattler-build."""
    if not platform:
        platform = ""
    os_part, *_rest = platform.split("-", maxsplit=1)
    arch = _rest[0] if _rest else ""

    # All platforms considered in this logic:
    # see https://github.com/conda/conda-build/blob/d27c97c11e2316905cefe24deebd3e445e853ece/tests/test_metadata.py#L588
    # linux-32: Linux x86 (i686, 32-bit)
    # linux-64:	Linux x86_64 (AMD/Intel 64-bit)
    # linux-aarch64:	Linux ARM v8 64-bit
    # linux-armv6l:	Linux ARM v6 32-bit
    # linux-armv7l:	Linux ARM v7 32-bit
    # linux-ppc64:	Linux PowerPC 64-bit, big-endian
    # linux-ppc64le:	Linux PowerPC 64-bit, little-endian
    # linux-riscv64:	Linux RISC-V 64-bit
    # linux-s390x:	Linux IBM Z / s390x 64-bit
    # osx-64:	macOS Intel 64-bit
    # osx-arm64:	macOS Apple-Silicon ARM64
    # win-32:	Windows x86 32-bit
    # win-64:	Windows x86_64 64-bit
    # win-arm64:	Windows on ARM 64-bit
    # freebsd-64:	FreeBSD x86_64 64-bit
    # emscripten-wasm32:	WebAssembly (Emscripten tool-chain)
    # wasi-wasm32:	WebAssembly for the WASI runtime
    # zos-z:	IBM z/OS

    flags: dict[str, bool | str] = {
        "target_platform": platform,
        # OS
        "linux": os_part == "linux",
        "osx": os_part == "osx",
        "win": os_part == "win",
        "emscripten": os_part == "emscripten",
        "wasi": os_part == "wasi",
        "freebsd": os_part == "freebsd",
        "zos": os_part == "zos",
        "unix": os_part in {"linux", "osx", "emscripten", "wasi", "freebsd", "zos"},
        # x86
        "x86": arch in {"32", "64"},
        "x86_64": arch in {"64"},
        # Arm
        "aarch64": arch in {"aarch64", "arm64"},
        "arm64": arch in {"aarch64", "arm64"},
        "armV6l": arch == "armv6l",
        "armV7l": arch == "armv7l",
        # Power / s390x
        "ppc64": arch == "ppc64",
        "ppc64le": arch == "ppc64le",
        "s390x": arch == "s390x",
        # RISC-V / WASM
        "riscv32": arch == "riscv32",
        "riscv64": arch == "riscv64",
        "wasm32": arch == "wasm32",
    }
    return flags


# -----------------------------------------------------------------------------#
# Core                                                                         #
# -----------------------------------------------------------------------------#
_ENV = jinja2.Environment()


def _eval_condition(expr: str, ctx: Mapping[str, Any]) -> bool:
    """Safe-ish evaluation of the selector expression using jinja2."""
    try:
        fn = _ENV.compile_expression(expr)
        return bool(fn(ctx))
    except Exception:
        # An invalid expression is treated as “False”
        return False


def _process_node(node: Any, ctx: Mapping[str, Any]) -> Any | None:
    """
    Recursively walk *node*,
    resolving any dict that has at least an ``"if"`` and ``"then"`` key.

    Returns
    -------
    * New object with selectors resolved
    * ``None`` --> caller will drop this element (condition false & no else)
    """
    # Selector handling --------------------------------------------------------
    if isinstance(node, Mapping) and "if" in node and "then" in node:
        cond = str(node["if"])
        branch = "then" if _eval_condition(cond, ctx) else "else"
        if branch in node:  # recurse into chosen branch
            return _process_node(node[branch], ctx)
        return None  # nothing chosen – drop

    # Recursion – dict ---------------------------------------------------------
    if isinstance(node, MutableMapping):
        out: dict[str, Any] = {}
        for k, v in node.items():
            new = _process_node(v, ctx)
            if new is not None:
                out[k] = new
        return out

    # Recursion – list ---------------------------------------------------------
    if isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
        out: list[Any] = []
        for item in node:
            new = _process_node(item, ctx)
            if new is None:
                continue
            # Flatten lists returned from selectors so the example in docs works
            if isinstance(new, list):
                out.extend(new)
            else:
                out.append(new)
        return out

    # Scalar – nothing to do ---------------------------------------------------
    return node


# Public entry point -----------------------------------------------------------
def evaluate_selectors(
    data: Any,
    *,
    target_platform: str,
) -> Any:
    """
    Return *data* with all rattler-build selectors evaluated.

    Parameters
    ----------
    data : Any
        Parsed YAML object (``ruamel`` or ``PyYAML``).
    target_platform : str
        ``linux-64``, ``osx-arm64``, etc.).

    Notes
    -----
    * Unknown variables inside the condition evaluate to *False*.
    * The “then” branch can be a scalar, mapping or list.
      If it is a list, items are *spliced* into the parent list so that
      multi-item examples from the rattler-build docs work naturally.
    """
    ctx = _platform_flags(target_platform)

    return _process_node(copy.deepcopy(data), ctx)
