# Changelog

All notable changes to ForgeAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (0.y.z during initial development).

## [Unreleased]

### Added
- Reserved for next release.

## [0.3.0] - 2026-08-23

Stabilization milestone — no product features, only structure/hygiene.

### Added
- `LICENSE` (MIT) — `Copyright (c) 2026 Tharun Sivamani`.
- `app/__version__.py` as single source of truth; synced `pyproject.toml:7`, `app/core/config.py:16`, `frontend/package.json:3`, `README.md`.
- `.env.example` at repo root (all `app/core/config.py` settings documented).
- `.editorconfig` and `.dockerignore`.
- `Makefile` with `check`/`test`/`lint`/`format`/`run`/`openapi`/`frontend` targets.
- `.pre-commit-config.yaml` (ruff + ruff-format + trailing-whitespace, end-of-file, yaml, merge-conflict).
- `.github/workflows/ci.yml` — backend (uv + ruff + pytest) and frontend (npm ci + build) on push/PR.
- `.github/ISSUE_TEMPLATE/` (bug_report, feature_request, config), `PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS`, `dependabot.yml`.
- `AGENTS.md` — agent/harness instructions for AI contributors.
- `CITATION.cff`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SECURITY.md`, `CONTRIBUTING.md`.
- `examples/` — moved 7 root smoke scripts (`test_*.py` → `examples/*_demo.py`) + `examples/README.md`; `tests/` remains CI-only (`pyproject.toml:40`).
- `infra/terraform/` skeleton (`main.tf`, `variables.tf`, `outputs.tf`, `envs/{dev,prod}/`, `modules/`).
- `docs/ARCHITECTURE.md` and `docs/PLUGIN_SDK.md` stubs + `openapi.json` generation via `make openapi`.
- `scripts/bump_version.py` — single-command version bump across 4 files.
- New tests: `tests/test_version_single_source.py`, `tests/test_stable_structure.py`, `tests/test_env_example.py` (see `tests/` for stable-structure guarantees).

### Changed
- `.gitignore` — stop ignoring `uv.lock` (commit lockfile for reproducible builds).
- `README.md` — badges, `uv sync`/`uv run` workflow, version `0.2.1 → 0.3.0`, updated Quick start and Testing sections.
- `pyproject.toml` — version `0.2.1 → 0.3.0`, added `project.license`, `project.urls`, `tool.ruff.format` sections.
- `app/core/config.py` — `APP_VERSION` now imports from `app.__version__`.
- `frontend/package.json` — version `0.1.0 → 0.3.0`.

### Fixed
- Toolchain drift: documented `uv` as canonical toolchain; `Dockerfile` now uses `uv sync --frozen` (no longer `pip install -r requirements.txt` only).
- Version drift: single source eliminates 4-file manual sync.

### Removed
- 7 smoke scripts from repo root (relocated to `examples/`).

## [0.2.1] - 2026-08-22

### Added
- Chat loop autonomy, soft users/RBAC, token stats, SSE streaming, sandbox status, LLM profiles API/UI, tool schemas.

### Security
- Calculator AST whitelisting, terminal injection protection, sandbox strictness, contextvars isolation, `SecretStr` for API keys.

## [0.1.0] - 2026-08-10 (approx)

- Initial harness with kernel, runtime, agents, storage, and Next.js console.
