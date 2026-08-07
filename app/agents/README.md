# `app/agents/`

Agents decide *what* should happen. They never import concrete tools directly for discovery — they go through the kernel/registry.

## Files

| File | Purpose |
|------|---------|
| `base.py` | Abstract `BaseAgent` with `async run(user_input) -> ToolResult` |
| `planner.py` | Main planner: LLM router (auto) or keyword selector + argument building |
| `runner.py` | Legacy multi-step harness (prefer `chat_loop`) |
| `chat_loop.py` | **Product autonomy**: LLM decides tools until final answer (async-safe context) |
| `research.py` | Research-focused agent (prefers search) |
| `coding.py` | Coding-focused agent (python/filesystem) |
| `reviewer.py` | Lightweight result review/approval notes |
| `executor.py` | Explicit `tool: args` executor |
| `orchestrator.py` | Routes to specialized agents, then reviews output |

## Autonomous example

```python
from app.agents.runner import agent_runner

run = await agent_runner.start("calculate 2+2", auto_approve=True)
# poll agent_runner.get(run.run_id) or subscribe to SSE
```

See [docs/AUTONOMOUS.md](../../docs/AUTONOMOUS.md).

## Examples

```python
import asyncio
from app.agents.planner import PlannerAgent

async def main():
    planner = PlannerAgent()
    result = await planner.run("calculate 2 + 2")
    print(result.output)

asyncio.run(main())
```

```python
from app.agents.orchestrator import MultiAgentOrchestrator

orch = MultiAgentOrchestrator()
result = await orch.run("research Python asyncio")
print(result.output["agent"], result.output["review"])
```
