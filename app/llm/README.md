# LLM providers

Provider-agnostic chat/completions with failover via `LLMRouter`, plus persistent **profiles** under `FORGE_HOME/llm/`.

| File | Role |
|------|------|
| `base.py` | `BaseLLM` + `LLMResponse` (`content`, `thinking`, tool calls, tokens) |
| `profiles.py` | Named profiles, active selection, model autofetch |
| `factory.py` | Provider factory from resolved profile/env |
| `router.py` | Primary + fallback routing |
| `openai_provider.py` | OpenAI / OpenAI-compatible Chat Completions |
| `anthropic_provider.py` | Anthropic Messages |
| `ollama_provider.py` | Local Ollama `/api/chat` (tools + thinking models) |
| `vllm_provider.py` | OpenAI-compatible vLLM |

## Profiles (preferred)

```bash
forge setup
forge profile list
forge profile use ollama-local
forge chat --profile ollama-local "hi"
```

Stored at `{FORGE_HOME}/llm/profiles.json` + `active.json`.

## Env fallbacks

```env
LLM_PROVIDER=ollama
MODEL_NAME=qwen3-vl:2b-thinking
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_THINK=true
```

Thinking models (e.g. Qwen3 `*-thinking`) return a separate `thinking` field. ForgeAI stores it on assistant message metadata and shows a collapsible Thought block in the UI.

```python
from app.llm.factory import get_llm

llm = get_llm()  # uses active profile
response = await llm.chat([{"role": "user", "content": "Hello!"}])
print(response.thinking)
print(response.content)
```
