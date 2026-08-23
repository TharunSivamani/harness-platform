#!/usr/bin/env python3
"""Bump version across app/__version__.py, pyproject.toml, frontend/package.json, README.md, CITATION.cff."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# very loose semver check — allow 0.3.0, 0.3.0-rc1, etc.
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([-.+].+)?$")


def bump(version: str) -> None:
    if not SEMVER_RE.match(version):
        sys.exit(f"Invalid version '{version}' — expected semver like 0.3.1")

    # 1. app/__version__.py
    version_py = ROOT / "app" / "__version__.py"
    version_py.write_text(
        f'"""Single source of truth for ForgeAI version."""\n\n__version__ = "{version}"\n__all__ = ["__version__"]\n',
        encoding="utf-8",
    )
    print(f"updated {version_py}")

    # 2. pyproject.toml — version = "..."
    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    new_text, n = re.subn(
        r'^version = ".*"', f'version = "{version}"', text, count=1, flags=re.MULTILINE
    )
    if n == 0:
        sys.exit("Could not find version line in pyproject.toml")
    pyproject.write_text(new_text, encoding="utf-8")
    print(f"updated {pyproject}")

    # 3. frontend/package.json
    pkg = ROOT / "frontend" / "package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    data["version"] = version
    pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"updated {pkg}")

    # 4. README.md — **Version:** 0.x.y
    readme = ROOT / "README.md"
    if readme.exists():
        txt = readme.read_text(encoding="utf-8")
        txt2, m = re.subn(r"\*\*Version:\*\* .+", f"**Version:** {version}", txt, count=1)
        if m:
            readme.write_text(txt2, encoding="utf-8")
            print(f"updated {readme}")
        else:
            print(f"skip {readme} (no Version line)")

    # 5. CITATION.cff — version: ...
    cff = ROOT / "CITATION.cff"
    if cff.exists():
        txt = cff.read_text(encoding="utf-8")
        txt2, m = re.subn(r"^version: .+", f"version: {version}", txt, count=1, flags=re.MULTILINE)
        if m:
            cff.write_text(txt2, encoding="utf-8")
            print(f"updated {cff}")

    print(
        f'\nBumped to {version} — verify with: uv run python -c "from app.__version__ import __version__; print(__version__)"'
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <new-version>", file=sys.stderr)
        print(f"  e.g. {sys.argv[0]} 0.3.1", file=sys.stderr)
        sys.exit(2)
    bump(sys.argv[1].strip())
