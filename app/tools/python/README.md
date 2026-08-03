# `app/tools/python/`

Restricted Python expression evaluator (AST whitelist, no imports).

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `tool = PythonTool()` |
| `tool.py` | Safe expression evaluator + `PythonTool` |

## Permissions

- `python.execute`

## Example

```python
result = await kernel.execute("python", code="sum([10, 20, 30])")
print(result.output)  # 60

# blocked:
result = await kernel.execute("python", code="__import__('os').system('dir')")
print(result.success)  # False
```
