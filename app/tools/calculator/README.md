# `app/tools/calculator/`

Evaluate mathematical expressions safely using AST-based whitelisting.

## Security

The calculator uses `RestrictedMathEvaluator` which parses expressions into an AST and only allows:
- Numeric literals (int, float, complex)
- Arithmetic operators (+, -, *, /, //, %, **)
- Comparison operators (==, !=, <, <=, >, >=)
- Whitelisted math functions (sqrt, sin, cos, log, abs, round, min, max, etc.)
- Math constants (pi, e, tau)

**Blocked**: `eval()`, `exec()`, `__import__`, attribute access, lambdas, comprehensions — preventing arbitrary code execution.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `tool = CalculatorTool()` |
| `tool.py` | `RestrictedMathEvaluator` + `CalculatorTool` implementation |

## Permissions

- `calculator.execute`

## Example

```python
from app.kernel.kernel import ExecutionKernel

kernel = ExecutionKernel()
result = await kernel.execute("calculator", expression="sqrt(16) + max(1, 2, 3) * 2")
print(result.output)  # 10.0

# Malicious expressions are blocked:
result = await kernel.execute("calculator", expression="__import__('os').system('id')")
print(result.success)  # False
print(result.error)    # "Name '__import__' is not allowed..."
```
