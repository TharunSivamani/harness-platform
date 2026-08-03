from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """
    Every tool in ForgeAI inherits from this class.
    """

    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool.
        """
        raise NotImplementedError