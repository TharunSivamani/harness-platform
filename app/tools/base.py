from abc import ABC, abstractmethod
from app.schemas.tool_result import ToolResult


class BaseTool(ABC):
    """
    Every tool in ForgeAI inherits from this class.
    """

    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool.
        """
        raise NotImplementedError