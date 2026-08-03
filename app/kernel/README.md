# `app/kernel/`

Execution kernel — the OS-like heart of ForgeAI.

## Files

| File | Purpose |
|------|---------|
| `kernel.py` | `ExecutionKernel`: permission check → resource lease → tool execute → record + events |

## Flow

```text
execute(tool_name, **kwargs)
  → Event: ToolSelected
  → PermissionEngine.require(...)
  → ResourceScheduler.acquire(...)
  → tool.execute(...)
  → ExecutionRecorder.record(...)
  → Event: ExecutionFinished
  → ResourceScheduler.release(...)
```

## Example

```python
from app.kernel.kernel import ExecutionKernel

kernel = ExecutionKernel(role="admin")
result = await kernel.execute("calculator", expression="5 * 8")
print(result.success, result.output)
```
