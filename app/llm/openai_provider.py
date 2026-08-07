from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.llm.base import BaseLLM, DeltaCallback, LLMResponse, StreamDelta


def _image_data_url(image: Any) -> str | None:
    """Build a data: URL from chat_loop image payloads (dict or raw b64 string)."""
    if isinstance(image, dict):
        data = image.get("data") or image.get("b64") or image.get("base64")
        mime = image.get("mime") or "image/png"
        if not data:
            return None
        if isinstance(data, str) and data.startswith("data:"):
            return data
        return f"data:{mime};base64,{data}"
    if isinstance(image, str) and image.strip():
        if image.startswith("data:"):
            return image
        return f"data:image/png;base64,{image}"
    return None


def normalize_openai_messages(
    messages: list[dict[str, Any]],
    *,
    system: str | None = None,
) -> list[dict[str, Any]]:
    """
    Convert ForgeAI message shape (including `images`) into OpenAI / LiteLLM
    multimodal chat.completions messages.
    """
    payload: list[dict[str, Any]] = []
    if system:
        payload.append({"role": "system", "content": system})

    for message in messages:
        role = message.get("role") or "user"
        item: dict[str, Any] = {"role": role}
        images = message.get("images") or []

        if role == "user" and images:
            parts: list[dict[str, Any]] = [
                {"type": "text", "text": message.get("content") or ""},
            ]
            for image in images:
                url = _image_data_url(image)
                if url:
                    parts.append({"type": "image_url", "image_url": {"url": url}})
            item["content"] = parts
        else:
            item["content"] = message.get("content")

        if role == "assistant" and message.get("tool_calls"):
            item["tool_calls"] = message["tool_calls"]
        if role == "tool" and message.get("tool_call_id"):
            item["tool_call_id"] = message["tool_call_id"]
            if message.get("name"):
                item["name"] = message["name"]

        # OpenAI rejects unknown top-level keys like `images` / `thinking`.
        payload.append(item)
    return payload


class OpenAIProvider(BaseLLM):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model or settings.MODEL_NAME
        self.api_key = api_key if api_key is not None else settings.get_openai_api_key()
        self.base_url = base_url
        if not self.api_key and self.base_url is not None:
            self.api_key = "EMPTY"
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
        on_delta: DeltaCallback | None = None,
    ) -> LLMResponse:
        if not self.api_key and self.base_url is None:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider.")

        payload_messages = normalize_openai_messages(messages, system=system)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": 0,
            "stream": bool(on_delta),
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if not on_delta:
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

        kwargs["stream_options"] = {"include_usage": True}
        content_parts: list[str] = []
        tool_acc: dict[int, dict[str, Any]] = {}
        prompt_tokens = 0
        completion_tokens = 0
        stream = await self.client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_parts.append(delta.content)
                await on_delta(StreamDelta(content=delta.content))
            for call in delta.tool_calls or []:
                entry = tool_acc.setdefault(
                    call.index,
                    {"id": call.id or f"tool-{call.index}", "name": "", "arguments": ""},
                )
                if call.id:
                    entry["id"] = call.id
                if call.function and call.function.name:
                    entry["name"] = call.function.name
                if call.function and call.function.arguments:
                    entry["arguments"] += call.function.arguments

        tool_calls = []
        for entry in tool_acc.values():
            raw_args = entry["arguments"] or "{}"
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed = {"raw": raw_args}
            tool_calls.append(
                {"id": entry["id"], "name": entry["name"], "arguments": parsed}
            )

        return LLMResponse(
            content="".join(content_parts) or None,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
