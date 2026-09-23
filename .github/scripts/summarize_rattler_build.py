#!/usr/bin/env python3
"""Write a compact rattler-build diagnostic for the GitHub job summary."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


ANSI_ESCAPE = re.compile(r"\x1b(?:[@-_][0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s*")
DIAGNOSTIC = re.compile(
    r"(?:Error:\s+×|fatal error(?:\s+[A-Z]+\d+)?:|\berror(?:\s+[A-Z]+\d+)?:|"
    r"CMake Error(?::|\s+at\b)|FAILED:|Patch application error|"
    r"Failed to resolve dependencies|Cannot solve the request)",
    re.IGNORECASE,
)
RECIPE_START = re.compile(r"Running build for recipe:|Build variant:")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--outcome", required=True)
    return parser.parse_args()


def clean(line: str) -> str:
    cleaned = TIMESTAMP.sub("", ANSI_ESCAPE.sub("", line)).rstrip()
    if len(cleaned) > 1_000:
        return cleaned[:1_000] + " … [line truncated]"
    return cleaned


def diagnostic_excerpt(lines: list[str]) -> list[str]:
    matches = [index for index, line in enumerate(lines) if DIAGNOSTIC.search(line)]
    if not matches:
        return []

    # Keep context around the last diagnostics. This includes multiline solver
    # explanations without flooding the GitHub summary with the complete log.
    selected: set[int] = set()
    for index in matches[-20:]:
        selected.update(range(max(0, index - 2), min(len(lines), index + 14)))

    # Name the recipe that produced the final diagnostic even when dependency
    # solver output has pushed its heading far outside the context window.
    first_diagnostic = matches[max(0, len(matches) - 20)]
    for index in range(first_diagnostic, -1, -1):
        if RECIPE_START.search(lines[index]):
            selected.add(index)
            break

    excerpt: list[str] = []
    previous = -2
    for index in sorted(selected):
        if previous >= 0 and index > previous + 1:
            excerpt.append("...")
        excerpt.append(lines[index])
        previous = index
    return excerpt[-160:]


def main() -> None:
    args = parse_args()
    run_url = (
        f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
        f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/"
        f"{os.environ.get('GITHUB_RUN_ID', '')}"
    )
    symbol = "✅" if args.outcome == "success" else "❌"

    print(f"## {symbol} rattler-build: `{args.platform}`")
    print()
    print(f"Outcome: **{args.outcome}** · [Open workflow run]({run_url})")

    if not args.log.is_file():
        print("\nNo build log was produced.")
        return

    lines = [clean(line) for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines()]
    excerpt = diagnostic_excerpt(lines)
    if not excerpt:
        print("\nNo error diagnostics were found in the build log.")
        return

    print("\n### Final diagnostics\n")
    print("```text")
    print("\n".join(excerpt))
    print("```")
    print("\nThe complete `rattler-build.log` is available in this run's artifacts.")


if __name__ == "__main__":
    main()
