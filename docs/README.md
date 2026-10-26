# Documentation

Architecture and developer notes for ForgeAI.

## Contents

- Root [`README.md`](../README.md) — product + quick start
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system diagram + request flows
- [`PLUGIN_SDK.md`](PLUGIN_SDK.md) — authoring a tool
- [`DATA.md`](DATA.md) — portable FORGE_HOME
- [`SANDBOXES.md`](SANDBOXES.md) — Hermes-style terminal/file tools
- [`AUTONOMOUS.md`](AUTONOMOUS.md) — chat-loop autonomy (historical)
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — branching + commits
- [`../SECURITY.md`](../SECURITY.md) — reporting + hardening
- [`../CHANGELOG.md`](../CHANGELOG.md) — version history

## Generated

- `openapi.json` at repo root — `make openapi` → `app.main:app.openapi()` (also served at `/docs`)
- `infra/terraform/` — IaC skeleton (stub until v0.7)
