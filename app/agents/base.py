from abc import ABC, abstractmethod

from app.schemas.tool_result import ToolResult


class BaseAgent(ABC):
    """
    Base class for all agents.
    """

    @abstractmethod
    async def run(self, user_input: str) -> ToolResult:
        raise NotImplementedError
