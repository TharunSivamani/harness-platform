# `app/storage/`

Portable persistence under `FORGE_HOME`.

## Files

| File | Purpose |
|------|---------|
| `paths.py` | `ForgePaths` layout helpers (`users/`, sessions, uploads, workspace) |
| `db.py` | SQLite users/sessions/messages/token_usage + jsonl mirrors |

## Example

```python
from app.storage.db import storage

user = storage.ensure_default_user()
session = storage.create_session(user["user_id"], title="Demo")
storage.add_message(
    session_id=session["session_id"], user_id=user["user_id"], role="user", content="hi"
)
print(storage.user_stats(user["user_id"]))
```
