"""Tests for version single-source guarantees (v0.3 scaffold)."""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_version_py() -> str:
    text = (ROOT / "app" / "__version__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert m, "app/__version__.py must define __version__"
    return m.group(1)


def test_version_py_exists_and_semver():
    v = _read_version_py()
    assert re.match(r"^\d+\.\d+\.\d+([-.+].*)?$", v), f"invalid semver: {v}"


def test_pyproject_version_matches():
    v = _read_version_py()
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["version"] == v


def test_config_app_version_matches():
    v = _read_version_py()
    # import after ensuring module loads — config imports __version__
    from app.core.config import settings

    assert v == settings.APP_VERSION


def test_frontend_package_version_matches():
    v = _read_version_py()
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == v, f"frontend {pkg['version']} != {v}"


def test_readme_version_matches():
    v = _read_version_py()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"**Version:** {v}" in readme


def test_app_main_version_matches():
    v = _read_version_py()
    from app.main import app

    # FastAPI version at app creation comes from settings.APP_VERSION
    assert app.version == v


def test_citation_version_matches():
    v = _read_version_py()
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f"version: {v}" in text
