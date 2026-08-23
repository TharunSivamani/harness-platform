# AGENTS.md — Instructions for AI Agents (and humans) working in this repo

This is the canonical agent guide. `CLAUDE.md` (if present) should symlink or re-export this file.

## Stack

- Backend: FastAPI (`app/main.py`), Python 3.11+, `uv` toolchain. Never use bare `pip`.
- Frontend: Next.js 15 + React 19 (`frontend/`).
- Storage: SQLite at `FORGE_HOME/forge.db` (`app/storage/`).
- Sandbox: `SANDBOX_BACKEND=auto|docker|local` (`app/runtime/sandbox.py`).

## Essential Commands

```bash
uv sync --all-extras          # install
uv run pytest -q              # tests — only tests/ runs in CI (pyproject.toml:40)
uv run ruff check .           # lint
uv run ruff format --check .  # format check
uv run ruff check --fix . && uv run ruff format .  # fix
uv run uvicorn app.main:app --reload --port 8000
make check                    # lint + format check + pytest
make openapi                  # regenerates openapi.json
```

Manual demos are in `examples/` — run with `uv run python examples/<demo>.py`. Do not add `test_*.py` at repo root.

## Project Conventions

- **Version** is single-sourced in `app/__version__.py`. Bump with `make bump V=0.3.1` or `uv run python scripts/bump_version.py 0.3.1` — updates `pyproject.toml`, `app/__version__.py`, `frontend/package.json`, `README.md`, `CITATION.cff`.
- **Secrets** are `SecretStr` in `app/core/config.py`. Use `.get_secret_value()` only when needed; never log secrets. Copy `.env.example` → `.env` locally.
- **Branches**: `main` (protected) ← `dev` ← `feature/*` / `bugfix/*` / `chore/*`. Never push to `main` directly.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`). Run `make check` before pushing.
- **Tools** live under `app/tools/<name>/tool.py` and are autodiscovered via `app/tools/loader.py`. See `app/tools/README.md` and `docs/PLUGIN_SDK.md`.
- **Pre-commit**: `pre-commit install` — hooks run ruff, ruff-format, trailing-whitespace, end-of-file, yaml, merge-conflict.

## What to Update When You Change...

| Change | Also update |
|--------|-------------|
| Routes in `app/main.py` | `openapi.json` via `make openapi`, `docs/ARCHITECTURE.md` |
| Runtime/kernel/agents | `docs/ARCHITECTURE.md` |
| New tool | `app/tools/<name>/README.md`, `examples/` demo, `tests/` coverage |
| Config env var | `.env.example`, `app/core/config.py`, `docs/DATA.md` |
| Version | `app/__version__.py` + bump script (never hand-edit 4 files) |

## Safety

- Do not commit `.env`, `data/`, `forgeai.db`, or `data/llm/secrets.json` (see `.gitignore`).
- `SANDBOX_BACKEND=docker` fails closed if Docker is missing — do not downgrade to `local` for untrusted code.
- Terminal tool blocks `; && |` etc. — treat sandbox as the real boundary, not the allowlist.

## Docs

- `README.md` — product + quick start
- `docs/ARCHITECTURE.md` — system diagram + flows
- `docs/PLUGIN_SDK.md` — tool author guide
- `docs/DATA.md` / `docs/SANDBOXES.md` / `docs/AUTONOMOUS.md` — subsystems
- `CONTRIBUTING.md` — contributor workflow
- `analysis.md` — stability audit (historical)
