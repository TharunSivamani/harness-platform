from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.llm.base import BaseLLM, DeltaCallback, LLMResponse, StreamDelta

_THINK_TAG_RE = re.compile(
    r"<think(?:ing)?>(.*?)</think(?:ing)?>",
    re.DOTALL | re.IGNORECASE,
)


def _split_thinking(content: str | None, thinking: str | None) -> tuple[str | None, str | None]:
    """Prefer native thinking field; also peel <think> tags from content."""
    text = content or ""
    extracted = (thinking or "").strip() or None

    if text and _THINK_TAG_RE.search(text):
        chunks = [
            match.group(1).strip()
            for match in _THINK_TAG_RE.finditer(text)
            if match.group(1).strip()
        ]
        if chunks:
            tagged = "\n\n".join(chunks)
            extracted = f"{extracted}\n\n{tagged}".strip() if extracted else tagged
        text = _THINK_TAG_RE.sub("", text).strip()

    return (text or None), extracted


class OllamaProvider(BaseLLM):
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model or settings.MODEL_NAME
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    async def complete(self, prompt: str, system: str | None = None) -> str:
        response = await self.chat(
            [{"role": "user", "content": prompt}],
            system=system,
        )
        return response.content or ""

    def _normalize_messages(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
    ) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        if system:
            payload.append({"role": "system", "content": system})

        for message in messages:
            role = message.get("role") or "user"
            item: dict[str, Any] = {
                "role": role,
                "content": message.get("content") or "",
            }
            thinking = message.get("thinking")
            if thinking:
                item["thinking"] = thinking
            images = message.get("images")
            if images:
                # Ollama expects raw base64 strings (no data: prefix).
                normalized: list[str] = []
                for image in images:
                    if isinstance(image, dict):
                        data = image.get("data") or image.get("b64") or image.get("base64")
                        if isinstance(data, str) and data:
                            if data.startswith("data:") and "," in data:
                                data = data.split(",", 1)[1]
                            normalized.append(data)
                    elif isinstance(image, str) and image.strip():
                        data = image
                        if data.startswith("data:") and "," in data:
                            data = data.split(",", 1)[1]
                        normalized.append(data)
                if normalized:
                    item["images"] = normalized
            if role == "assistant" and message.get("tool_calls"):
                item["tool_calls"] = message["tool_calls"]
            if role == "tool" and message.get("tool_call_id"):
                item["tool_name"] = message.get("name") or message.get("tool_name")
            payload.append(item)
        return payload

    def _parse_tool_calls(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            name = function.get("name") or call.get("name")
            if not name:
                continue
            arguments = function.get("arguments", call.get("arguments", {}))
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": arguments}
            if not isinstance(arguments, dict):
                arguments = {"value": arguments}
            tool_calls.append(
                {
                    "id": call.get("id") or f"ollama-{uuid.uuid4().hex[:10]}",
                    "name": name,
                    "arguments": arguments,
                }
            )
        return tool_calls

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        on_delta: DeltaCallback | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._normalize_messages(messages, system=system),
            "stream": True,
            "think": bool(settings.OLLAMA_THINK),
        }
        if tools:
            payload["tools"] = tools

        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        prompt_tokens = 0
        completion_tokens = 0
        last_chunk: dict[str, Any] = {}

        async with (
            httpx.AsyncClient(timeout=300.0) as client,
            client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                last_chunk = chunk
                message = chunk.get("message") or {}

                thinking_delta = message.get("thinking") or ""
                content_delta = message.get("content") or ""
                if thinking_delta:
                    thinking_parts.append(thinking_delta)
                    if on_delta:
                        await on_delta(StreamDelta(thinking=thinking_delta))
                if content_delta:
                    content_parts.append(content_delta)
                    if on_delta:
                        await on_delta(StreamDelta(content=content_delta))

                if message.get("tool_calls"):
                    tool_calls = self._parse_tool_calls(message)

                if chunk.get("done"):
                    prompt_tokens = int(chunk.get("prompt_eval_count") or 0)
                    completion_tokens = int(chunk.get("eval_count") or 0)

        content, thinking = _split_thinking(
            "".join(content_parts) or None,
            "".join(thinking_parts) or None,
        )

        return LLMResponse(
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw=last_chunk,
        )
