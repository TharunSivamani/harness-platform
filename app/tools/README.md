# `app/tools/`

Plugin tool ecosystem. Each **subpackage** exports `tool = SomeTool()` and is auto-discovered by the loader.

## Files

| File | Purpose |
|------|---------|
| `base.py` | `BaseTool` ABC (`manifest` + `execute`) |
| `registry.py` | In-memory tool registry + manifest discovery |
| `loader.py` | Package discovery / idempotent `load_plugins()` |
| `selector.py` | Keyword scoring tool selector |

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
