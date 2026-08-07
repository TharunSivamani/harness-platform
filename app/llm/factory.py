from __future__ import annotations

from app.llm.base import BaseLLM
from app.llm.profiles import ResolvedLLMConfig, resolve_llm_config


def get_llm(
    provider: str | None = None,
    *,
    profile: str | None = None,
    config: ResolvedLLMConfig | None = None,
) -> BaseLLM:
    """
    Build a provider client from the active/override profile (then env defaults).
    """
    resolved = config or resolve_llm_config(profile)
    name = (provider or resolved.provider).lower().strip()

    if name in {"openai", "openai_compatible", "litellm"}:
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=resolved.api_key,
            model=resolved.model,
            base_url=resolved.base_url,
        )

    if name == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=resolved.api_key, model=resolved.model)

    if name == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(model=resolved.model, base_url=resolved.base_url)

    if name == "vllm":
        from app.llm.vllm_provider import VLLMProvider

        return VLLMProvider(
            model=resolved.model,
            base_url=resolved.base_url,
            api_key=resolved.api_key or "EMPTY",
        )

    raise ValueError(f"Unsupported LLM provider: {name}")
