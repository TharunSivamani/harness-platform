# `app/llm/`

Provider-agnostic LLM layer with failover routing.

## Files

| File | Purpose |
|------|---------|
| `base.py` | `BaseLLM` interface (`complete`) |
| `factory.py` | `get_llm(provider)` factory |
| `router.py` | `LLMRouter` with primary + fallback providers |
| `openai_provider.py` | OpenAI Chat Completions |
| `anthropic_provider.py` | Anthropic Messages API |
| `ollama_provider.py` | Local Ollama `/api/generate` |
| `vllm_provider.py` | OpenAI-compatible vLLM endpoint |

## Examples

```python
from app.llm.factory import get_llm

llm = get_llm("ollama")
text = await llm.complete("Say hello", system="Be brief")
```

```python
from app.llm.router import llm_router

# tries OPENAI then fallbacks from settings.LLM_FALLBACK_PROVIDERS
text = await llm_router.complete("Return JSON only")
```
