# Contributing to ForgeAI

Thanks for contributing — this project aims to be a stable, portable agent harness.

## Quick Start

```bash
# 1. Fork and clone
git clone https://github.com/<you>/harness-platform.git
cd harness-platform

# 2. Toolchain — uv only (do not use pip directly)
uv sync --all-extras
cp .env.example .env   # fill secrets, never commit .env

# 3. Verify
make check              # ruff check + ruff format --check + pytest
make run                # uvicorn app.main:app --reload

# 4. Frontend
cd frontend && npm ci && npm run dev  # http://localhost:3000
```

## Branch Workflow

- `main` is protected — never push directly.
- `dev` is the integration branch.
- Branch from `dev`:
  - `feature/<kebab>` — new capability
  - `bugfix/<kebab>` — fix
  - `hotfix/<kebab>` — urgent fix from `main` (then merge back to `dev`)
  - `docs/<topic>` / `chore/<topic>`

```bash
git checkout dev && git pull origin dev
git checkout -b feature/my-feature
# ... work ...
make check
git commit -m "feat(scope): concise description"
git push -u origin feature/my-feature
# Open PR: feature/my-feature → dev
```

Releases: `dev → main` via PR, then `git tag vX.Y.Z && git push origin vX.Y.Z`.

## Commit Style

Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
Scope is optional but preferred: `feat(tools): add patch tool`.

## Code Standards

- Python 3.11+, `ruff` with line length 100 (`pyproject.toml:45-65`). Run `make format` before pushing.
- Pre-commit hooks: `pre-commit install` then `pre-commit run --all-files`.
- Tests: `uv run pytest -q` — CI only runs `tests/` (`pyproject.toml:40`). Manual demos live in `examples/`.
- Version: single source `app/__version__.py` — bump via `make bump` or `scripts/bump_version.py` (updates `pyproject.toml`, `app/__version__.py`, `frontend/package.json`, `README.md`).
- Secrets: use `SecretStr` in `app/core/config.py`; never log `get_secret_value()`.

## Adding a Tool

1. Create `app/tools/<name>/tool.py` implementing the tool interface (see `app/tools/README.md` and existing tools).
2. Register via autodiscovery under `app/tools/` (`app/tools/loader.py`, `app/tools/registry.py`).
3. Add `app/tools/<name>/README.md` and an `examples/<name>_demo.py` snippet.
4. Add tests in `tests/` — cover allow/deny, injection, and bounded-resource behavior.

## Adding an Agent / Runtime Change

- Update `docs/ARCHITECTURE.md` with the new flow.
- Add `docs/` sequence diagram if you touch `app/kernel/`, `app/runtime/`, or `app/agents/`.
- Export OpenAPI: `make openapi` → commit `openapi.json` if routes changed.

## Pull Request Checklist

- [ ] `make check` green
- [ ] Tests added/updated for new behavior
- [ ] `CHANGELOG.md` entry under `Unreleased`
- [ ] `docs/` updated if user-visible behavior changed
- [ ] No secrets or `.env` committed
- [ ] `frontend` built (`npm run build`) if UI touched

## Developer Certificate of Origin

By contributing you agree that your contributions are under the MIT license and you have the right to submit them (DCO).

## Code of Conduct

See `CODE_OF_CONDUCT.md`. Be respectful and constructive.
