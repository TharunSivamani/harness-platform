# Autonomous Agent Harness

ForgeAI's Claude-Code-style control loop lives in `app/agents/runner.py`.

## Loop

```text
goal
  → decide (LLM or heuristic)
  → optional approval gate
  → kernel.execute(tool)
  → append tool result to transcript
  → repeat until final / max_steps / failure
```

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/agent/autonomous` | Start a run |
| `GET` | `/agent/runs/{id}` | Snapshot |
| `GET` | `/agent/runs/{id}/stream` | SSE live events |
| `POST` | `/agent/runs/{id}/approve` | Resume after approval gate |

### Start

```bash
curl -X POST http://127.0.0.1:8000/agent/autonomous ^
  -H "Content-Type: application/json" ^
  -d "{\"goal\": \"calculate 2+2\", \"auto_approve\": true}"
```

### Stream

```bash
curl -N http://127.0.0.1:8000/agent/runs/<run_id>/stream
```

Events include: `RunStarted`, `StepPlanned`, `ApprovalRequired`, `ToolStarted`, `ToolFinished`, `RunCompleted`, `RunFailed`.

## UI

Open [http://localhost:3000/run](http://localhost:3000/run) for the live run console.

## Config

```env
AGENT_MAX_STEPS=8
AGENT_AUTO_APPROVE=true
AGENT_APPROVAL_TOOLS=terminal,filesystem,browser
```

When `AGENT_AUTO_APPROVE=false`, tools in `AGENT_APPROVAL_TOOLS` pause the run until `/approve`.
