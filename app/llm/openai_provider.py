from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.llm.base import BaseLLM, LLMResponse


class OpenAIProvider(BaseLLM):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model or settings.MODEL_NAME
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.base_url = base_url
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key or "MISSING_OPENAI_API_KEY",
                base_url=self.base_url,
            )
        return self._client

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
        if not self.api_key and self.base_url is None:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider.")

        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": 0,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0].message
        tool_calls = []
        for call in choice.tool_calls or []:
            args = call.function.arguments or "{}"
            try:
                parsed = json.loads(args)
            except json.JSONDecodeError:
                parsed = {"raw": args}
            tool_calls.append(
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": parsed,
                }
            )

        usage = getattr(response, "usage", None)
        return LLMResponse(
            content=choice.content,
            tool_calls=tool_calls,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            raw=response,
        )
