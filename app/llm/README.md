# LLM providers

Provider-agnostic chat/completions with failover via `LLMRouter`, plus persistent **profiles** under `FORGE_HOME/llm/`.

| File | Role |
|------|------|
| `base.py` | `BaseLLM` + `LLMResponse` (`content`, `thinking`, tool calls, tokens) |
| `profiles.py` | Named profiles, active selection, model autofetch, secrets separation |
| `factory.py` | Provider factory from resolved profile/env |
| `router.py` | Primary + fallback routing |
| `openai_provider.py` | OpenAI / OpenAI-compatible Chat Completions with tool calling |
| `anthropic_provider.py` | Anthropic Messages API with full tool-use support |
| `ollama_provider.py` | Local Ollama `/api/chat` (tools + thinking models) |
| `vllm_provider.py` | OpenAI-compatible vLLM |

## Provider Features

| Provider | Tool Calling | Streaming | Image Support |
|----------|-------------|-----------|---------------|
| OpenAI | ✅ Native | ✅ | ✅ |
| Anthropic | ✅ Native (tool_use) | ✅ | ✅ |
| Ollama | ✅ Native | ✅ | ✅ |
| vLLM | ✅ (via OpenAI compat) | ✅ | Depends |

## Secrets Storage

API keys are stored separately from profiles for security:
- `profiles.json` — Profile metadata (no secrets)
- `secrets.json` — API keys only (chmod 0600)

Legacy inline keys are auto-migrated on first load.

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
