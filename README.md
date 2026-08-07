# ForgeAI

Portable **ChatGPT-style agent workspace** with a Hermes-inspired tool runtime.

**Version:** 0.2.1

Autonomy is not a separate product endpoint: every chat turn asks the LLM what to do next. If it wants tools, it runs them; if it is done, it answers.

## Security Features

- **Safe expression evaluation**: Calculator uses AST-based whitelisting (no `eval()`)
- **Shell injection protection**: Terminal blocks metacharacters (`;`, `&&`, `|`, etc.)
- **Sandbox strictness**: `SANDBOX_BACKEND=docker` fails loudly if Docker unavailable
- **Async-safe context**: Session isolation using `contextvars` for concurrent requests
- **Secret protection**: API keys typed as `SecretStr` to prevent accidental logging

## Quick start

```bash
pip install -r requirements.txt
pip install -e .

# Launch API + Web UI together (opens browser)
forgeai ui
# aliases: forge ui · forge --webui · forgeai --webui

# Or run separately:
uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev

# CLI — LLM profiles live under FORGE_HOME (not one-shot env exports)
forge setup
forge profile list
forge profile use ollama-local

# CLI — operates on your current directory as the project root
cd /path/to/your/app
forge tools
forge chat "list the files in this project"
forge chat --profile ollama-local --project C:\path\to\app "summarize README"
forge            # interactive REPL
```

- UI: http://localhost:3000 — **LLM profiles** page (same store as `forge setup`); open a folder so tools edit that tree
- API docs: http://127.0.0.1:8000/docs
- Chat memory + LLM profiles: `./data` (`FORGE_HOME`); code root: session `project_root` / CLI cwd

## Product model

| Surface | Behavior |
|---------|----------|
| Web UI (`forgeai ui`) | Chat, LLM profiles setup, project folder, file tree, uploads, streaming |
| `forge` / `forgeai` CLI | Same chat loop + profile store; default project = cwd |
| Tools | Autodiscovered packages under `app/tools/` |
| Sandbox | `SANDBOX_BACKEND=auto` → Docker if available, else local host env |

### Hermes-style tools

- `terminal` — shell in project root (local/docker sandbox backend, with injection protection)
- `read_file` / `write_file` / `patch` — LLM supplies edits (prefer over shell heredocs)
- `calculator` — safe math evaluation via AST whitelisting
- plus python, search, browser, filesystem

### Portable state

Chats/prompts/tokens live under `FORGE_HOME`. The **project root** is separate: the folder you open in the UI or launch `forge` from. See [docs/DATA.md](docs/DATA.md) and [docs/SANDBOXES.md](docs/SANDBOXES.md).

### Soft users / RBAC

Local users with roles (`owner`/`member`/`viewer`). No cloud auth. Header `X-Forge-User` selects the profile.

### Token stats

Per message usage is recorded when the LLM returns usage; rollups available at:

- `GET /stats/me`
- `GET /sessions/{id}/stats`

## Core APIs

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/sessions` | Create session (`project_root` optional) |
| `PUT` | `/sessions/{id}/project` | Bind session to a folder |
| `GET` | `/sessions/{id}/project/tree` | List project files |
| `POST` | `/sessions/{id}/chat` | Chat turn (LLM tool loop until final) |
| `GET` | `/sessions/{id}/stream` | SSE tool/chat events |
| `POST` | `/sessions/{id}/upload` | Upload file/image into session |
| `GET` | `/sessions/{id}/files` | List uploads/workspace/artifacts |
| `GET` | `/llm/profiles` | List profiles + active/resolved |
| `POST` | `/llm/profiles` | Create/update profile |
| `POST` | `/llm/profiles/{name}/activate` | Set active profile |
| `DELETE` | `/llm/profiles/{name}` | Delete profile |
| `GET` | `/llm/providers` | Supported providers + default base URLs |
| `POST` | `/llm/models` | Autofetch models for provider/profile |
| `GET` | `/sandbox/status` | Effective sandbox backend |
| `GET` | `/stats/me` | User token stats |
| `GET` | `/tools` | Autodiscovered tools |

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run test suite
pytest tests/

# Run with coverage
pytest tests/ --cov=app
```

Tests cover security features (calculator AST, terminal injection, context isolation, sandbox strictness) and bounded data structures.

## Docs

- [DATA.md](docs/DATA.md) — portable home layout, secrets storage
- [SANDBOXES.md](docs/SANDBOXES.md) — terminal backends, Docker requirements
- [AUTONOMOUS.md](docs/AUTONOMOUS.md) — historical note; product path is chat loop
- Folder READMEs under `app/` and `frontend/`
