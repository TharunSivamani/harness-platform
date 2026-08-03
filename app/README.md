# `app/`

Root application package for ForgeAI.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Marks `app` as a Python package |
| `main.py` | FastAPI entrypoint: routes, startup hooks, agent/runtime wiring |

## Example

```bash
uvicorn app.main:app --reload
```

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
print(client.get("/health").json())
```
