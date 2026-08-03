# ForgeAI

Extensible **AI Agent Operating System** — a modular execution platform where planning, execution, memory, tools, and runtime services are independent modules.

> Planning, execution, memory, and tools should all be independent modules.

## What it is

ForgeAI is not a ChatGPT clone or LangChain wrapper. It is an AI infrastructure runtime with:

- Plugin-based tools
- Execution kernel with permissions, scheduling, and recording
- Sandboxed execution (local / Docker)
- Session workspaces and artifacts
- Event bus, state machine, and workflow engine
- Multi-provider LLM routing
- Multi-agent orchestration

## Quick start

```bash
pip install -r requirements.txt

# optional browser support
pip install playwright
playwright install chromium

# run API
uvicorn app.main:app --reload

# run UI (separate terminal)
cd frontend
npm install
npm run dev
```

- API docs: `http://127.0.0.1:8000/docs`
- Console UI: `http://localhost:3000`

### Docker

```bash
docker compose up --build
```

## Architecture

```text
User
  │
REST API
  │
Session / Memory / State Machine
  │
Planner / Multi-Agent Orchestrator
  │
Execution Kernel
  │
Permissions → Scheduler → Events → Recorder
  │
Sandbox Manager → Tool Registry → Tools
  │
Artifacts / Workspace / Metrics
```

## Core API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat` | Chat with task state tracking |
| `POST` | `/agent/run` | Run planner agent |
| `POST` | `/agent/multi` | Multi-agent orchestration |
| `POST` | `/workflow` | Run research→python→review workflow |
| `POST` | `/tool` | Execute a tool directly |
| `POST` | `/upload` | Upload content into a workspace |
| `GET` | `/artifacts` | List artifacts |
| `GET` | `/artifacts/{id}` | Download artifact |
| `GET` | `/sessions` | List sessions |
| `POST` | `/session` | Create session + workspace |
| `GET` | `/tools` | Discover tool manifests |
| `GET` | `/metrics` | Runtime metrics |
| `GET` | `/events` | Event bus history |
| `GET` | `/health` | Health check |

### Example: chat

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"calculate 12 * (5 + 8)\"}"
```

### Example: direct tool call

```bash
curl -X POST http://127.0.0.1:8000/tool ^
  -H "Content-Type: application/json" ^
  -d "{\"tool\": \"python\", \"arguments\": {\"code\": \"sum([1,2,3])\"}}"
```

## Configuration

Set via `.env` or environment variables (see `app/core/config.py`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `PLANNER_MODE` | `auto` | `auto` / `llm` / `keyword` |
| `LLM_PROVIDER` | `openai` | Primary provider |
| `LLM_FALLBACK_PROVIDERS` | `ollama,vllm` | Failover chain |
| `SANDBOX_BACKEND` | `local` | `local` or `docker` |
| `API_KEY` | unset | Optional API key gate |
| `DEFAULT_ROLE` | `admin` | Permission role |
| `WORKSPACE_ROOT` | `./workspace` | Workspace root |
| `ARTIFACT_ROOT` | `./artifacts` | Artifact store |

## Project layout

```text
app/
  agents/         # Planner + specialized agents
  core/           # Config + logging
  kernel/         # Execution kernel
  llm/            # Providers + router
  memory/         # Session + long-term memory
  observability/  # Metrics
  runtime/        # Sandbox, workflow, queue, etc.
  schemas/        # Shared models
  security/       # Auth / roles
  storage/        # SQLite storage
  tools/          # Plugin tools
```

Each folder has its own `README.md` with file-level descriptions and examples.

## Roadmap status

| Phase | Status |
|-------|--------|
| 1 Foundation | Done |
| 2 Plugin framework | Done |
| 3 Core tools | Done (calculator, python, filesystem, terminal, search, browser) |
| 4 LLM integration | Done (OpenAI, Anthropic, Ollama, vLLM + router) |
| 5 Memory | Done (session + long-term keyword memory) |
| 6 Multi-agent | Done (planner/research/coding/reviewer/executor) |
| Priority 0 runtime | Done (sandbox, workspace, artifacts, events, state, workflow, queue, permissions, scheduler, recorder) |
| Enterprise (full OTel/K8s/frontend) | Partial foundations |

## License

Educational / personal project.
