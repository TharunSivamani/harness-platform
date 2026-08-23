# `app/core/`

Cross-cutting application configuration and logging.

## Files

| File | Purpose |
|------|---------|
| `config.py` | Pydantic settings (`Settings`) loaded from env/`.env` |
| `logger.py` | Shared `forge-ai` logger |

## Security Features

API keys are typed as `SecretStr` to prevent accidental logging:

```python
from app.core.config import settings

# Safe access via helper methods:
api_key = settings.get_openai_api_key()  # Returns str | None
anthropic_key = settings.get_anthropic_api_key()
server_key = settings.get_api_key()

# Direct access returns SecretStr (won't log plaintext):
print(settings.OPENAI_API_KEY)  # SecretStr('**********')
```

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
SANDBOX_BACKEND=docker
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
API_KEY=your-server-secret
```
