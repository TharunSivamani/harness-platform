# ForgeAI

Portable **ChatGPT-style agent workspace** with a Hermes-inspired tool runtime.

Autonomy is not a separate product endpoint: every chat turn asks the LLM what to do next. If it wants tools, it runs them; if it is done, it answers.

## Quick start

```bash
pip install -r requirements.txt
pip install -e .

# API
uvicorn app.main:app --reload --port 8000

# UI
cd frontend && npm install && npm run dev

# CLI
forge tools
forge chat "calculate 2+2"
forge            # interactive REPL
```

- UI: http://localhost:3000
- API docs: http://127.0.0.1:8000/docs
- Data root: `./data` (`FORGE_HOME`)

## Product model

| Surface | Behavior |
|---------|----------|
| Web chat | Sidebar sessions, uploads, inline tool steps, token stats |
| `forge` CLI | Same chat loop + autodiscovered tools |
| Tools | Autodiscovered packages under `app/tools/` |

### Hermes-style tools

- `terminal` — shell in session workspace (local/docker sandbox backend)
- `read_file` / `write_file` / `patch` — LLM supplies edits (prefer over shell heredocs)
- plus calculator, python, search, browser, filesystem

### Portable state

All chats/prompts/files/tokens live under `FORGE_HOME`. Copy the folder to migrate. See [docs/DATA.md](docs/DATA.md).

### Soft users / RBAC

Local users with roles (`owner`/`member`/`viewer`). No cloud auth. Header `X-Forge-User` selects the profile.

### Token stats

Per message usage is recorded when the LLM returns usage; rollups available at:

- `GET /stats/me`
- `GET /sessions/{id}/stats`

## Core APIs

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/sessions` | Create chat session |
| `GET` | `/sessions` | List sessions |
| `POST` | `/sessions/{id}/chat` | Chat turn (LLM tool loop until final) |
| `GET` | `/sessions/{id}/stream` | SSE tool/chat events |
| `POST` | `/sessions/{id}/upload` | Upload file/image into session |
| `GET` | `/sessions/{id}/files` | List uploads/workspace/artifacts |
| `GET` | `/stats/me` | User token stats |
| `GET` | `/tools` | Autodiscovered tools |

## Docs

- [DATA.md](docs/DATA.md) — portable home layout
- [SANDBOXES.md](docs/SANDBOXES.md) — terminal backends
- [AUTONOMOUS.md](docs/AUTONOMOUS.md) — historical note; product path is chat loop
- Folder READMEs under `app/` and `frontend/`
