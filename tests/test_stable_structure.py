"""Stable-structure guarantees — no root smoke scripts, required files, Makefile/CI parity."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "LICENSE",
    "README.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "CITATION.cff",
    ".env.example",
    ".editorconfig",
    ".dockerignore",
    "Makefile",
    ".pre-commit-config.yaml",
    "AGENTS.md",
    "CLAUDE.md",
    "app/__version__.py",
    "pyproject.toml",
    "uv.lock",
    "docs/ARCHITECTURE.md",
    "docs/PLUGIN_SDK.md",
    "infra/terraform/README.md",
    "infra/terraform/main.tf",
    "infra/terraform/variables.tf",
    "infra/terraform/outputs.tf",
    ".github/workflows/ci.yml",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    "examples/README.md",
    "scripts/bump_version.py",
]

FORBIDDEN_ROOT_PATTERNS = [
    "test_*.py",  # smoke scripts must be in examples/
]


def test_required_files_exist():
    missing = [p for p in REQUIRED_FILES if not (ROOT / p).exists()]
    assert not missing, f"Missing stable files: {missing}"


def test_no_root_smoke_scripts():
    # root test_*.py should not exist — they belong in examples/
    roots = list(ROOT.glob("test_*.py"))
    assert not roots, f"Root smoke scripts found (move to examples/): {[p.name for p in roots]}"


def test_examples_contain_expected_demos():
    expected = {
        "kernel_demo.py",
        "runtime_demo.py",
        "llm_demo.py",
        "memory_demo.py",
        "planner_demo.py",
        "autonomous_demo.py",
        "multi_agent_demo.py",
    }
    actual = {p.name for p in (ROOT / "examples").glob("*.py")}
    assert expected.issubset(actual), f"Missing demos: {expected - actual}"


def test_pyproject_testpaths_is_tests_only():
    import tomllib

    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


def test_gitignore_does_not_ignore_uv_lock():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    # should not have an active "uv.lock" ignore line
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped == "uv.lock":
            raise AssertionError(".gitignore must not ignore uv.lock — commit lockfile")


def test_license_is_mit():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Copyright (c) 2026" in text


def test_makefile_has_required_targets():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ["check:", "test:", "lint:", "format:", "openapi:", "bump:"]:
        assert target in text, f"Makefile missing target {target}"


def test_pre_commit_has_ruff():
    text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "ruff" in text.lower()
    assert "trailing-whitespace" in text


def test_ci_workflow_has_backend_and_frontend():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "backend" in text.lower()
    assert "frontend" in text.lower()
    assert "ruff" in text.lower()
    assert "pytest" in text.lower()
    assert "setup-uv" in text


def test_editorconfig_exists_and_has_python_section():
    text = (ROOT / ".editorconfig").read_text(encoding="utf-8")
    assert "[*.py]" in text
    assert "indent_size = 4" in text


def test_dockerignore_has_essential_entries():
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for entry in ["__pycache__", ".venv", "node_modules", ".git"]:
        assert entry in text


def test_infra_skeleton_exists():
    assert (ROOT / "infra" / "terraform" / "envs" / "dev").is_dir()
    assert (ROOT / "infra" / "terraform" / "envs" / "prod").is_dir()
    assert (ROOT / "infra" / "terraform" / "modules").is_dir()


def test_docs_architecture_mentions_core_modules():
    text = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for mod in ["app/main.py", "app/kernel", "app/runtime", "app/llm"]:
        assert mod in text, f"ARCHITECTURE.md missing {mod}"


def test_pyproject_has_license_and_urls():
    import tomllib

    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    assert "license" in data["project"]
    assert "urls" in data["project"]


def test_examples_do_not_import_pytest_as_test_suite():
    # demos should not be collected as tests — ensure they don't define test_* that pytest would pick
    for p in (ROOT / "examples").glob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "def test_" not in text, (
            f"{p.name} should not define test_* (CI would miscollect if moved)"
        )
