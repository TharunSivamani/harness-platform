# `app/tools/`

Plugin tool ecosystem. Each **subpackage** exports `tool = SomeTool()` and is auto-discovered by the loader.

## Files

| File | Purpose |
|------|---------|
| `base.py` | `BaseTool` ABC (`manifest` + `execute`) |
| `registry.py` | In-memory tool registry + manifest discovery |
| `loader.py` | Package discovery / idempotent `load_plugins()` |
| `selector.py` | Keyword scoring tool selector |
| `context.py` | Session context using `contextvars` for async safety |

## Session Context

Tools access the current user/session via `contextvars`-based context (async-safe):

```python
from app.tools.context import (
    session_context_scope,
    current_user_id,
    current_session_id,
    current_project_root,
)

# In chat loop (automatic):
async with session_context_scope(user_id, session_id, project_root):
    result = await tool.execute(...)


# In tool implementation:
def get_workspace():
    return Path(current_project_root() or "/tmp")
```

This ensures concurrent async requests are isolated — one user's context never leaks to another.

## Plugin contract

```text
app/tools/my_tool/
  __init__.py   # tool = MyTool()
  tool.py       # class MyTool(BaseTool)
```

## Examples

```python
from app.tools.loader import load_plugins, registry

load_plugins()
print(registry.list_tools())
print([m.name for m in registry.discover()])
```

```python
from app.tools.selector import ToolSelector

selector = ToolSelector()
tool = selector.select("search for asyncio")
print(tool.manifest.name if tool else None)
```
