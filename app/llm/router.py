from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.agents.errors import ChatCancelled
from app.core.config import settings
from app.core.logger import logger
from app.llm.base import BaseLLM, DeltaCallback, LLMResponse
from app.llm.factory import get_llm
from app.llm.profiles import resolve_llm_config
from app.runtime.events import event_bus


class LLMRouter:
    """
    Routes chat/completions using the active LLM profile.

    When a profile is active, only that provider is used (no silent failover to
    env defaults like Ollama). Optional LLM_FALLBACK_PROVIDERS still apply only
    when no profile is active, or when explicitly configured.
    """

    def __init__(
        self,
        primary: str | None = None,
        fallbacks: list[str] | None = None,
        profile: str | None = None,
    ):
        self.profile = profile
        self._primary_override = primary.lower() if primary else None
        self.fallbacks = fallbacks if fallbacks is not None else settings.llm_fallback_providers

    def _providers(self) -> list[str]:
        resolved = resolve_llm_config(self.profile)
        primary = (self._primary_override or resolved.provider).lower()

        # Active/explicit profile: stay on that provider unless fallbacks are set.
        if resolved.profile_name and not self.fallbacks and not self._primary_override:
            return [primary]

        ordered = [primary, *[item for item in self.fallbacks if item != primary]]
        usable: list[str] = []
        for name in ordered:
            if name == resolved.provider:
                if name == "openai" and not resolved.api_key and not resolved.base_url:
                    continue
                if name == "anthropic" and not resolved.api_key:
                    continue
                usable.append(name)
                continue
            if name == "openai" and not settings.OPENAI_API_KEY:
                continue
            if name == "anthropic" and not settings.ANTHROPIC_API_KEY:
                continue
            usable.append(name)
        return usable or [primary]

    async def complete(self, prompt: str, system: str | None = None) -> str:
        response = await self.chat(
            [{"role": "user", "content": prompt}],
            system=system,
        )
        return response.content or ""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        on_delta: DeltaCallback | None = None,
    ) -> LLMResponse:
        errors: list[str] = []
        resolved = resolve_llm_config(self.profile)
        for provider_name in self._providers():
            try:
                await event_bus.publish(
                    "LLMProviderSelected",
                    {
                        "provider": provider_name,
                        "profile": resolved.profile_name,
                        "model": resolved.model if provider_name == resolved.provider else None,
                        "base_url": resolved.base_url if provider_name == resolved.provider else None,
                    },
                )
                if provider_name == resolved.provider:
                    provider: BaseLLM = get_llm(config=resolved)
                else:
                    # Fallbacks use env/settings for that provider — never mix the
                    # active profile's LiteLLM URL into an Ollama client.
                    from app.llm.profiles import ResolvedLLMConfig, default_base_url

                    fallback_key = None
                    if provider_name in {"openai", "vllm", "openai_compatible", "litellm"}:
                        fallback_key = settings.OPENAI_API_KEY
                    elif provider_name == "anthropic":
                        fallback_key = settings.ANTHROPIC_API_KEY
                    if provider_name in {"vllm", "openai_compatible", "litellm"}:
                        fallback_key = fallback_key or "EMPTY"

                    provider = get_llm(
                        config=ResolvedLLMConfig(
                            provider=provider_name,
                            model=settings.MODEL_NAME,
                            api_key=fallback_key,
                            base_url=default_base_url(provider_name),
                            profile_name=None,
                        )
                    )
                result = await provider.chat(
                    messages,
                    tools=tools,
                    system=system,
                    on_delta=on_delta,
                )
                if tools and not result.tool_calls and result.content:
                    parsed = self._parse_json_tool_decision(result.content)
                    if parsed:
                        result.tool_calls = parsed.get("tool_calls", [])
                        if parsed.get("content") is not None:
                            result.content = parsed["content"]
                await event_bus.publish(
                    "LLMCompletionFinished",
                    {
                        "provider": provider_name,
                        "profile": resolved.profile_name,
                        "tool_calls": len(result.tool_calls),
                        "prompt_tokens": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                        "has_thinking": bool(result.thinking),
                    },
                )
                return result
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, (ChatCancelled, asyncio.CancelledError)):
                    raise
                message = f"{provider_name}: {exc}"
                errors.append(message)
                logger.warning("LLM provider failed: %s", message)
        raise RuntimeError("All LLM providers failed: " + " | ".join(errors))

    def _parse_json_tool_decision(self, raw: str) -> dict[str, Any] | None:
        text = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        if not isinstance(data, dict):
            return None
        if data.get("action") == "tool" and data.get("tool"):
            return {
                "content": data.get("thought"),
                "tool_calls": [
                    {
                        "id": "json-tool-1",
                        "name": data["tool"],
                        "arguments": data.get("arguments") or {},
                    }
                ],
            }
        if data.get("action") == "final":
            return {"content": data.get("output") or data.get("content") or "", "tool_calls": []}
        return None


llm_router = LLMRouter()
