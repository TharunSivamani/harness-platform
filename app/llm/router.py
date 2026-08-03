from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import settings
from app.core.logger import logger
from app.llm.base import BaseLLM, LLMResponse
from app.llm.factory import get_llm
from app.runtime.events import event_bus


class LLMRouter:
    """
    Routes chat/completions across providers with failover.
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
        usable = []
        for name in ordered:
            if name == "openai" and not settings.OPENAI_API_KEY and self.primary != "vllm":
                # still allow vllm via openai client with base_url
                if name == self.primary and settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
                    continue
                if name == "openai" and not settings.OPENAI_API_KEY:
                    continue
            if name == "anthropic" and not settings.ANTHROPIC_API_KEY:
                continue
            usable.append(name)
        return usable or ordered

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
    ) -> LLMResponse:
        errors: list[str] = []
        for provider_name in self._providers():
            try:
                await event_bus.publish("LLMProviderSelected", {"provider": provider_name})
                provider: BaseLLM = get_llm(provider_name)
                result = await provider.chat(messages, tools=tools, system=system)
                # JSON tool-call fallback for providers without native tools
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
                        "tool_calls": len(result.tool_calls),
                        "prompt_tokens": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                    },
                )
                return result
            except Exception as exc:  # noqa: BLE001
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
