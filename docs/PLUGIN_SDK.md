# Plugin SDK — Authoring a Tool

Tools are autodiscovered from `app/tools/<name>/` (`app/tools/loader.py:load_plugins`).

## Minimal Tool

```
app/tools/mytool/
├── __init__.py      # re-export tool instance
├── tool.py          # implement Tool
└── README.md        # describe usage
```

`tool.py` example:

```python
from app.tools.base import Tool
from app.schemas.tool_result import ToolResult
from app.tools.context import ToolContext


class MyTool(Tool):
    name = "mytool"
    description = "One-line description for LLM"
    # JSON schema for args — LLM must conform
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "what to do"},
            "max_results": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }

    async def execute(
        self, query: str, max_results: int = 5, *, context: ToolContext
    ) -> ToolResult:
        # context has: user_id, session_id, project_root, workspace_path, etc.
        # Enforce project_root boundary: use context.resolve_path() or workspace_paths helpers
        # Return ToolResult — kernel records it and feeds back to LLM
        return ToolResult(success=True, output=f"did {query}", data={"count": 1})
```

Register by importing in `app/tools/mytool/__init__.py`:

```python
from .tool import MyTool

tool = MyTool()
```

`load_plugins()` imports each `app/tools/<name>` and registers via `registry`.

## Contracts

- **Input validation**: prefer pydantic or explicit checks; raise `ValueError` for bad args (mapped to 400).
- **Path safety**: always resolve under `context.project_root` via `app/tools/workspace_paths.py` or `_resolve_under_project` pattern. Reject `..` traversal.
- **Sandbox**: for shell/python use `app/runtime/sandbox.py` — never `subprocess` directly. Respect `SANDBOX_BACKEND` and `SANDBOX_FOR_*` flags.
- **Output**: `ToolResult(success, output, data, error)` — keep `output` concise for LLM context window; put large data in `data`.
- **Security**: block injection (see `terminal/tool.py:_validate_command_security`), AST-whitelist eval (see `calculator/tool.py`).

## LLM Exposure

Add `name`, `description`, `parameters` — these become OpenAI tool schemas via `app/llm/*` → `registry.discover()` → `GET /tools`. Test with:

```bash
uv run python -c "from app.tools.loader import load_plugins, registry; load_plugins(); print([t.name for t in registry.discover()])"
uv run pytest tests/ -k mytool
```

## Checklist

- [ ] `app/tools/<name>/tool.py` + `README.md`
- [ ] `examples/<name>_demo.py` runnable via `uv run python examples/...`
- [ ] `tests/test_<name>*.py` covering allow/deny, injection, bounds
- [ ] `docs/ARCHITECTURE.md` updated if new runtime capability
- [ ] `make check` green
