#!/usr/bin/env python3
"""Bump the version string inside pyproject.toml.

Usage:
    python scripts/bump_version.py <major|minor|micro|patch>
"""

import re
import sys
from pathlib import Path


def bump_version(bump_type: str) -> None:
    """Read pyproject.toml, increment the requested version component, and write it back."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("ERROR: pyproject.toml not found. Run this script from the project root.")
        sys.exit(1)

    content = pyproject_path.read_text(encoding="utf-8")

    match = re.search(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', content, re.MULTILINE)
    if not match:
        print("ERROR: Could not locate a version = \"X.Y.Z\" line in pyproject.toml.")
        sys.exit(1)

    major, minor, micro = int(match.group(1)), int(match.group(2)), int(match.group(3))
    old_version = f"{major}.{minor}.{micro}"

    if bump_type == "major":
        major += 1
        minor = 0
        micro = 0
    elif bump_type == "minor":
        minor += 1
        micro = 0
    elif bump_type in ("micro", "patch"):
        micro += 1
    else:
        print(f"ERROR: Unknown bump type '{bump_type}'. Use major, minor, micro, or patch.")
        sys.exit(1)

    new_version = f"{major}.{minor}.{micro}"

    # Use re.sub targeting the exact matched span so we never accidentally
    # replace a version string that appears elsewhere (e.g. in a comment or
    # as a dependency constraint).
    new_content = re.sub(
        r'^(version\s*=\s*)"[^"]+"',
        f'\\1"{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    pyproject_path.write_text(new_content, encoding="utf-8")
    print(f"Version bumped: {old_version} → {new_version}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: bump_version.py <major|minor|micro|patch>")
        sys.exit(1)

    bump_version(sys.argv[1])
