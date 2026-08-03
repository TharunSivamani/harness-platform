from app.core.config import settings
from app.llm.base import BaseLLM


def get_llm(provider: str | None = None) -> BaseLLM:
    name = (provider or settings.LLM_PROVIDER).lower().strip()

    if name == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()

    if name == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()

    if name == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider()

    if name == "vllm":
        from app.llm.vllm_provider import VLLMProvider

        return VLLMProvider()

    raise ValueError(f"Unsupported LLM provider: {name}")
