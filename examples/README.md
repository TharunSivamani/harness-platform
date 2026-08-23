# Examples — Manual Smoke Demos (not CI)

These are manual demos moved from the repo root (`test_*.py`) to keep the root clean.
CI only runs `tests/` (`pyproject.toml: testpaths = ["tests"]`). These are for local exploration.

## Run

```bash
uv sync --all-extras
uv run python examples/kernel_demo.py
uv run python examples/runtime_demo.py
uv run python examples/llm_demo.py
uv run python examples/memory_demo.py
uv run python examples/planner_demo.py
uv run python examples/autonomous_demo.py
uv run python examples/multi_agent_demo.py
```

## Map

| Demo | Previous root file | What it shows |
|------|-------------------|---------------|
| `kernel_demo.py` | `test_kernel.py` | `ExecutionKernel` with calculator, python, filesystem, terminal, search |
| `runtime_demo.py` | `test_runtime.py` | Workspace, artifacts, sandbox, state machine, events |
| `llm_demo.py` | `test_llm.py` | LLM provider factory (openai/ollama/vllm) wiring — no remote call |
| `memory_demo.py` | `test_memory.py` | Session + long-term memory recall |
| `planner_demo.py` | `test_planner.py` | `PlannerAgent` on 4 sample prompts |
| `autonomous_demo.py` | `test_autonomous.py` | `agent_runner` start + poll loop |
| `multi_agent_demo.py` | `test_multi_agent.py` | `MultiAgentOrchestrator` simple run |

Keep `examples/` runnable via `uv run python examples/...` — update this README when adding a new demo.
