# `app/tools/calculator/`

Evaluate mathematical expressions.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `tool = CalculatorTool()` |
| `tool.py` | `CalculatorTool` implementation + manifest |

## Permissions

- `calculator.execute`

## Example

```python
from app.kernel.kernel import ExecutionKernel

kernel = ExecutionKernel()
result = await kernel.execute("calculator", expression="12 * (5 + 8)")
print(result.output)  # 156
```
