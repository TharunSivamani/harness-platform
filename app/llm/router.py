from __future__ import annotations

from app.core.config import settings
from app.core.logger import logger
from app.llm.base import BaseLLM
from app.llm.factory import get_llm
from app.runtime.events import event_bus


class LLMRouter:
    """
    Routes completions across providers with failover.
    """

    def __init__(
        self,
        primary: str | None = None,
        fallbacks: list[str] | None = None,
    ):
        self.primary = (primary or settings.LLM_PROVIDER).lower()
        self.fallbacks = fallbacks or settings.llm_fallback_providers

    def _providers(self) -> list[str]:
        ordered = [self.primary, *[item for item in self.fallbacks if item != self.primary]]
        return ordered

    async def complete(self, prompt: str, system: str | None = None) -> str:
        errors: list[str] = []
        for provider_name in self._providers():
            try:
                await event_bus.publish(
                    "LLMProviderSelected",
                    {"provider": provider_name},
                )
                provider: BaseLLM = get_llm(provider_name)
                text = await provider.complete(prompt=prompt, system=system)
                await event_bus.publish(
                    "LLMCompletionFinished",
                    {"provider": provider_name, "chars": len(text)},
                )
                return text
            except Exception as exc:  # noqa: BLE001
                message = f"{provider_name}: {exc}"
                errors.append(message)
                logger.warning("LLM provider failed: %s", message)

        raise RuntimeError("All LLM providers failed: " + " | ".join(errors))


llm_router = LLMRouter()
