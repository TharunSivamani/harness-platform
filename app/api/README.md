# `app/api/`

Reserved for split FastAPI routers as the API surface grows.

Currently routes live in `app/main.py` for simplicity. Future structure:

```text
app/api/routes/
  chat.py
  tools.py
  artifacts.py
  sessions.py
```

## Example (future)

```python
from fastapi import APIRouter

router = APIRouter(prefix="/tools")

@router.get("")
async def list_tools():
    ...
```
