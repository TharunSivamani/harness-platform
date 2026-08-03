# `app/storage/`

Persistence layer for development (SQLite). Production can later swap to Postgres.

## Files

| File | Purpose |
|------|---------|
| `db.py` | `Storage` — key/value store + audit log table |

## Examples

```python
from app.storage.db import storage

storage.set("last_user", {"id": "u1"})
print(storage.get("last_user"))

storage.audit("tool.execute", {"tool": "calculator", "ok": True})
```

Database file defaults to `./forgeai.db` via `DATABASE_URL=sqlite:///./forgeai.db`.
