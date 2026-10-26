"""
Anthropic Claude provider with full tool-calling support.

SECURITY FIX: Previously this provider inherited BaseLLM.chat() which silently
dropped all tools - users got a plain chatbot with no warning that agentic
tool use wasn't happening. Now implements proper Anthropic Messages API
with native tool_use support.
"""

import json
from typing import Any

import httpx

from app.core.config import settings
from app.llm.base import BaseLLM, DeltaCallback, LLMResponse, StreamDelta


def _convert_openai_tools_to_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert OpenAI-style tool definitions to Anthropic format.

    OpenAI format:
        {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}

    Anthropic format:
        {"name": "...", "description": "...", "input_schema": {...}}
    """
    anthropic_tools = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        func = tool.get("function", {})
        anthropic_tools.append(
            {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return anthropic_tools


def _convert_messages_to_anthropic(
    messages: list[dict[str, Any]],
    system: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Convert OpenAI-style messages to Anthropic format.

    Key differences:
    - Anthropic uses 'system' as a top-level param, not in messages
    - Anthropic tool results use 'tool_result' content blocks
    - Anthropic tool calls are 'tool_use' content blocks
    """
    anthropic_messages: list[dict[str, Any]] = []
    effective_system = system

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            # Collect system messages into the system param
            if effective_system:
                effective_system = f"{effective_system}\n\n{content}"
            else:
                effective_system = content
            continue

        if role == "tool":
            # Convert tool result to Anthropic format
            tool_call_id = msg.get("tool_call_id", "")
            anthropic_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": content,
                        }
                    ],
                }
            )
            continue

        if role == "assistant":
            # Check for tool calls in assistant message
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                content_blocks: list[dict[str, Any]] = []
                if content:
                    content_blocks.append({"type": "text", "text": content})
                for call in tool_calls:
                    func = call.get("function", {})
                    args_str = func.get("arguments", "{}")
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except json.JSONDecodeError:
                        args = {"raw": args_str}
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.get("id", ""),
                            "name": func.get("name", ""),
                            "input": args,
                        }
                    )
                anthropic_messages.append(
                    {
                        "role": "assistant",
                        "content": content_blocks,
                    }
                )
            else:
                anthropic_messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                    }
                )
            continue

        # User messages - handle images if present
        images = msg.get("images", [])
        if images:
            content_blocks = []
            if content:
                content_blocks.append({"type": "text", "text": content})
            for img in images:
                if isinstance(img, dict):
                    data = img.get("data") or img.get("b64") or img.get("base64", "")
                    mime = img.get("mime", "image/png")
                else:
                    data = str(img)
                    mime = "image/png"
                # Remove data: URL prefix if present
                if data.startswith("data:"):
                    # Extract base64 part after comma
                    if "," in data:
                        data = data.split(",", 1)[1]
                content_blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": data,
                        },
                    }
                )
            anthropic_messages.append({"role": "user", "content": content_blocks})
        else:
            anthropic_messages.append({"role": "user", "content": content})

    return anthropic_messages, effective_system


class AnthropicProvider(BaseLLM):
    """
    Anthropic Claude provider with full Messages API support including tool calling.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.get_anthropic_api_key()
        self.model = model or settings.MODEL_NAME
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for AnthropicProvider.")

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Simple completion without tools."""
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
        """
        Full chat completion with streaming and tool-calling support.

        Implements proper Anthropic Messages API:
        - Converts OpenAI-style messages and tools to Anthropic format
        - Supports streaming via on_delta callback
        - Returns tool_use blocks as tool_calls in LLMResponse
        """
        # Convert messages and tools to Anthropic format
        anthropic_messages, effective_system = _convert_messages_to_anthropic(messages, system)
        anthropic_tools = _convert_openai_tools_to_anthropic(tools or [])

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": anthropic_messages,
        }
        if effective_system:
            payload["system"] = effective_system
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        timeout = httpx.Timeout(120.0, connect=10.0)

        if not on_delta:
            # Non-streaming request
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            return self._parse_response(data)

        # Streaming request
        payload["stream"] = True

        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        current_tool: dict[str, Any] | None = None
        tool_input_buffer: str = ""
        usage_input = 0
        usage_output = 0

        async with (
            httpx.AsyncClient(timeout=timeout) as client,
            client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers=self._headers(),
                json=payload,
            ) as response,
        ):
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                try:
                    event_data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                event_type = event_data.get("type", "")

                if event_type == "content_block_start":
                    block = event_data.get("content_block", {})
                    if block.get("type") == "tool_use":
                        current_tool = {
                            "id": block.get("id", ""),
                            "name": block.get("name", ""),
                        }
                        tool_input_buffer = ""

                elif event_type == "content_block_delta":
                    delta = event_data.get("delta", {})
                    delta_type = delta.get("type", "")

                    if delta_type == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            content_parts.append(text)
                            await on_delta(StreamDelta(content=text))

                    elif delta_type == "input_json_delta":
                        partial = delta.get("partial_json", "")
                        tool_input_buffer += partial

                elif event_type == "content_block_stop":
                    if current_tool is not None:
                        try:
                            args = json.loads(tool_input_buffer) if tool_input_buffer else {}
                        except json.JSONDecodeError:
                            args = {"raw": tool_input_buffer}
                        tool_calls.append(
                            {
                                "id": current_tool["id"],
                                "name": current_tool["name"],
                                "arguments": args,
                            }
                        )
                        current_tool = None
                        tool_input_buffer = ""

                elif event_type == "message_delta":
                    usage = event_data.get("usage", {})
                    usage_output = usage.get("output_tokens", usage_output)

                elif event_type == "message_start":
                    msg = event_data.get("message", {})
                    usage = msg.get("usage", {})
                    usage_input = usage.get("input_tokens", 0)

        return LLMResponse(
            content="".join(content_parts) or None,
            tool_calls=tool_calls,
            prompt_tokens=usage_input,
            completion_tokens=usage_output,
        )

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse a non-streamed Anthropic response."""
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in data.get("content", []):
            block_type = block.get("type", "")

            if block_type == "text":
                content_parts.append(block.get("text", ""))

            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {}),
                    }
                )

        usage = data.get("usage", {})

        return LLMResponse(
            content="\n".join(content_parts).strip() or None,
            tool_calls=tool_calls,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            raw=data,
        )
