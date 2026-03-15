from __future__ import annotations
import sys
import platform
from subprocess import call

FAIL_UNDER = 60

WIN = platform.system() == "Windows"

SKIP = [
    # as of https://github.com/conda-forge/jupyter_core-feedstock/pull/103
    "not_on_path",
    "path_priority",
    "argv0",
]

SKIP_K = f"""not ({" or ".join(SKIP)})"""

PYTEST = ["pytest", "-vv", "--tb=long", "--color=yes", "-k", SKIP_K]

COV_TEST = ["coverage", "run", "--source", "jupyter_core", "-m", *PYTEST]
COV_REPORT = [
    "coverage",
    "report",
    "--show-missing",
    "--skip-covered",
    f"--fail-under={FAIL_UNDER}",
]


def do(args: list[str]) -> int:
    print("\n>>>", *args, flush=True)
    return call(args)


if __name__ == "__main__":
    sys.exit(do(COV_TEST) or do(COV_REPORT))
