# Architecture — ForgeAI v0.3

## C4 Context (Level 1)

```
User ──► Next.js Console (frontend/src) ──► FastAPI (app/main.py) ──► Agent Runtime
                                        │                            ├─ app/kernel/kernel.py  (ExecutionKernel)
                                        │                            ├─ app/tools/*           (autodiscovered)
                                        │                            ├─ app/runtime/sandbox   (docker/local)
                                        │                            ├─ app/agents/chat_loop  (LLM tool loop)
                                        │                            └─ app/llm/*             (provider router)
                                        └─► SQLite (FORGE_HOME/forge.db) + FS (data/, workspace/, artifacts/)
```

## Request Flows

### 1. Chat turn (`POST /sessions/{id}/chat`)
```
Client → FastAPI /chat → app/agents/chat_loop.py:run()
  → resolve_llm_config() → app/llm/router.py → provider (openai/ollama/anthropic/vllm)
  → loop: LLM decides {tool_calls} → ExecutionKernel.execute(tool, args) → app/tools/<name>/tool.py
        → sandbox (terminal/python) or direct (calculator/read_file/patch/search/browser)
        → append tool_result to messages → re-ask LLM
  → final answer → storage (app/storage/db.py) → SSE via /stream (app/runtime/events.py)
```

### 2. Project-scoped operations

- Session carries `project_root` (`PUT /sessions/{id}/project`). All file/sandbox ops are resolved under it (`_resolve_under_project` in `app/main.py:113`).
- Tree/files: `GET /project/tree` / `/project/file` with `is_relative_to` guard.

### 3. LLM profiles

- Store: `~/.forgeai` or `FORGEAI_CONFIG` (`app/core/config.py:forgeai_config_home`) → `app/llm/profiles.py`.
- Active profile resolves provider/base_url/model/api_key; `/llm/models` proxies `GET /v1/models` for LiteLLM.

### 4. Sandbox

- `SANDBOX_BACKEND=auto` → docker if available else local (`app/runtime/sandbox.py:resolve_backend`).
- `SANDBOX_BACKEND=docker` fails closed if Docker missing (tested in `tests/test_sandbox_strictness.py`).
- Terminal allowlist + metacharacter block (`app/tools/terminal/tool.py:_validate_command_security`).

## Module Map

| Path | Responsibility |
|------|---------------|
| `app/main.py` | FastAPI app, 35 routes, startup, CORS, SSE, upload/workspace bridging |
| `app/core/config.py` | `Settings` (Pydantic BaseSettings, `SecretStr`), `APP_VERSION` from `app/__version__.py` |
| `app/core/logger.py` | structured logging |
| `app/kernel/kernel.py` | `ExecutionKernel` — tool dispatch, bounded resources |
| `app/tools/` | Tool contracts (`base.py`, `registry.py`, `loader.py`) + 9 tools (`calculator`, `terminal`, `python`, `search`, `browser`, `filesystem`, `read_file`, `write_file`, `patch`) |
| `app/runtime/` | `sandbox`, `workspace`, `artifacts`, `events`, `queue`, `state`, `recorder`, `permissions` |
| `app/agents/` | `chat_loop`, `planner`, `orchestrator`, `runner` (autonomous), `coding/research/reviewer` |
| `app/memory/` | `session` + `long_term` + `system` |
| `app/llm/` | `factory`, `router`, providers (`openai`, `ollama`, `anthropic`, `vllm`), `profiles` |
| `app/storage/` | `db.py` (SQLite), `paths.py` (FORGE_HOME layout) |
| `app/cli/` | `forge`/`forgeai` entrypoints, REPL, profile setup, webui launcher |
| `app/schemas/` | `tool_manifest`, `tool_result` pydantic models |
| `app/security/auth.py` | `require_api_key` (optional header check) |
| `frontend/src/` | Next.js app router, chat + sessions + LLM profiles UI |
| `infra/terraform/` | IaC skeleton (stub until v0.7) |

## Data Layout

- `FORGE_HOME` (default `./data`) → `forge.db`, `uploads/`, `artifacts/`, `workspace/`, `retained_artifacts/`
- `~/.forgeai` → `llm/profiles.json`, `llm/secrets.json` (encrypted at rest in future)
- Per-session: `FORGE_HOME/users/{user_id}/sessions/{session_id}/{uploads,workspace,artifacts,meta.json}`

## OpenAPI

- Generated via `make openapi` → `openapi.json` (from `app.main:app.openapi()`). Also served at `/docs` (Swagger) and `/openapi.json`.

## Future Split

`app/main.py:1-737` is monolithic. Planned: `app/api/routes/{sessions,llm,sandbox,files,stats}.py` + `app/api/deps.py` (auth, user resolve). Stub dir `app/api/routes/` already exists — no logic moved in v0.3 to keep diff reviewable.
