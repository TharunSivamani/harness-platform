# `app/core/`

Cross-cutting application configuration and logging.

## Files

| File | Purpose |
|------|---------|
| `config.py` | Pydantic settings (`Settings`) loaded from env/`.env` |
| `logger.py` | Shared `forge-ai` logger |

## Examples

```python
from app.core.config import settings

print(settings.APP_NAME, settings.SANDBOX_BACKEND)
print(settings.terminal_allowlist)
```

```python
from app.core.logger import logger

logger.info("ForgeAI started")
```

Create a `.env`:

```env
PLANNER_MODE=keyword
SANDBOX_BACKEND=auto
OPENAI_API_KEY=sk-...
```
