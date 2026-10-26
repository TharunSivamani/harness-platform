# CLAUDE.md — See AGENTS.md

This file re-exports `AGENTS.md` for Claude Code compatibility.

> Canonical instructions: [`AGENTS.md`](AGENTS.md)

- Run `uv run pytest -q` before committing.
- Only `tests/` is CI; demos live in `examples/`.
- Version single source: `app/__version__.py` → `make bump V=...`
- Branches: `main` ← `dev` ← `feature/*`
