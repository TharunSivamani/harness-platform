from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """
    Provider-agnostic LLM interface.
    """

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError
