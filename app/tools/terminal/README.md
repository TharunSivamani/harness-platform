# `app/tools/terminal/`

Run allowlisted shell commands inside the workspace directory.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `tool = TerminalTool()` |
| `tool.py` | Allowlist + timeout shell execution |

## Permissions

- `terminal.execute`

## Example

```python
result = await kernel.execute("terminal", command="echo forge-ok")
print(result.output)
```

Configure allowlist via `TERMINAL_ALLOWLIST` in settings.
