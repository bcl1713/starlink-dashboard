#!/usr/bin/env python3
"""Block on repository links; report remote availability as an advisory."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_links(root: Path, inputs: list[str]) -> int:
    root = root.resolve()
    internal = [
        "lychee",
        "--no-progress",
        "--offline",
        "--scheme",
        "file",
        # Explicit inclusion overrides the legacy file:// exclusion in .lycheeignore.
        "--include",
        "^file://",
        "--include-fragments",
        "--root-dir",
        str(root),
        *inputs,
    ]
    print("Checking internal documentation files and anchors (required)", flush=True)
    try:
        result = subprocess.run(internal, cwd=root, check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Internal documentation link check failed: {error}", file=sys.stderr)
        return 2
    if result.returncode:
        return result.returncode

    external = [
        "lychee",
        "--no-progress",
        "--scheme",
        "http",
        "--scheme",
        "https",
        "--max-retries",
        "0",
        "--timeout",
        "10",
        *inputs,
    ]
    print("Checking external documentation links (advisory)", flush=True)
    try:
        result = subprocess.run(external, cwd=root, check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        detail = str(error)
    else:
        if not result.returncode:
            return 0
        detail = f"Lychee exited with status {result.returncode}; see link report above"
    print(
        f"::warning title=External documentation links::External check did not pass: {detail}. "
        "Internal files and anchors passed; external availability is nonblocking.",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-dir", type=Path, default=ROOT)
    parser.add_argument("inputs", nargs="*", default=["docs/"])
    args = parser.parse_args()
    return check_links(args.root_dir, args.inputs)


if __name__ == "__main__":
    raise SystemExit(main())
