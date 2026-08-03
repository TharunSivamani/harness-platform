from abc import ABC, abstractmethod

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult


class BaseTool(ABC):

    manifest: ToolManifest

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError