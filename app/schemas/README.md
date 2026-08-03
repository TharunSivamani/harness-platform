# `app/schemas/`

Shared Pydantic models used across tools, agents, and APIs.

## Files

| File | Purpose |
|------|---------|
| `tool_result.py` | Standard tool response (`success`, `output`, `error`, `execution_time`, `metadata`) |
| `tool_manifest.py` | Tool discovery metadata (`name`, `description`, `keywords`, `priority`, `permissions`) |

## Examples

```python
from app.schemas.tool_result import ToolResult

result = ToolResult(success=True, output=42, execution_time=0.001)
print(result.model_dump_json(indent=2))
```

```python
from app.schemas.tool_manifest import ToolManifest

manifest = ToolManifest(
    name="weather",
    description="Get weather",
    keywords=["weather", "forecast"],
    permissions=["network"],
)
```
