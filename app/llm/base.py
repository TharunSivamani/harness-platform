from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: Any = None


class BaseLLM(ABC):
    """
    Provider-agnostic LLM interface.
    """

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        """
        Default fallback: flatten to a single completion (no native tool calling).
        """
        prompt_parts = []
        for message in messages:
            prompt_parts.append(f"{message.get('role')}: {message.get('content')}")
        text = await self.complete("\n".join(prompt_parts), system=system)
        return LLMResponse(content=text)
