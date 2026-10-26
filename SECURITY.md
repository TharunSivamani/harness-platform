# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| < 0.3   | :x:                |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Email the maintainers or use GitHub's private vulnerability reporting (Security → Report a vulnerability). Include:

- Affected version / commit
- Reproduction steps or PoC
- Impact assessment (sandbox escape, secret leakage, injection, etc.)

We aim to acknowledge within 72 hours and provide a fix or mitigation plan within 14 days.

## Security Model

ForgeAI is a local-first agent harness. Key assumptions:

- **No cloud auth** — soft users via `X-Forge-User` header; do not expose the API to the public internet without a reverse proxy / auth layer.
- **Secrets** — API keys are stored as `SecretStr` (`app/core/config.py`) and under `~/.forgeai` (`FORGEAI_CONFIG`). Never commit `.env` or `data/llm/secrets.json`. See `.env.example`.
- **Sandbox** — `SANDBOX_BACKEND=auto` prefers Docker; `SANDBOX_BACKEND=docker` fails closed if Docker is unavailable. `SANDBOX_BACKEND=local` runs on the host — do not use for untrusted code.
- **Terminal** — blocks shell metacharacters (`; && |` etc.) and allowlists executables (`TERMINAL_ALLOWLIST`). This is defense-in-depth, not a security boundary — treat the sandbox as the boundary.
- **Calculator** — AST-whitelisted expression evaluation; no `eval()`.

## Hardening Checklist for Operators

- [ ] Run with `SANDBOX_BACKEND=docker` in any untrusted workload.
- [ ] Set `API_KEY` and require it at the proxy; see `app/security/auth.py`.
- [ ] Restrict `CORS_ORIGINS` to your frontend origin only.
- [ ] Mount `FORGE_HOME` on encrypted storage; back up `forge.db` separately.
- [ ] Keep `playwright` browser sandboxed (no `--no-sandbox` in production).
