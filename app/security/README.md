# `app/security/`

Authentication and role resolution for API requests.

## Files

| File | Purpose |
|------|---------|
| `auth.py` | Optional `X-API-Key` gate + `X-Forge-Role` role header helper |

## Security Features

- **API Key Protection**: Server API key typed as `SecretStr` to prevent accidental logging
- **Role-based Access**: Roles map to tool permissions
- **Header-based Auth**: Simple `X-API-Key` and `X-Forge-Role` headers

## Configuration

```env
API_KEY=your-secret-key  # Enables API key requirement
```

When `API_KEY` is set, all requests must include the `X-API-Key` header.

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
