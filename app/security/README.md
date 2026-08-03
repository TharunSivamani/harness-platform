# `app/security/`

Authentication and role resolution for API requests.

## Files

| File | Purpose |
|------|---------|
| `auth.py` | Optional `X-API-Key` gate + `X-Forge-Role` role header helper |

## Examples

```bash
# When API_KEY is set in env:
curl http://127.0.0.1:8000/health -H "X-API-Key: secret"

# Choose permission role for tool execution:
curl -X POST http://127.0.0.1:8000/tool ^
  -H "Content-Type: application/json" ^
  -H "X-Forge-Role: developer" ^
  -d "{\"tool\": \"calculator\", \"arguments\": {\"expression\": \"1+1\"}}"
```

Roles map to permissions in `app/runtime/permissions.py` (`viewer`, `developer`, `admin`).
