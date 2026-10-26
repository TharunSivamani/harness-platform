from app.schemas.tool_manifest import ToolManifest
from app.tools.base import BaseTool


class ToolRegistry:
    """
    Central registry for all available tools.

    Responsibilities:
    - Register tools
    - Retrieve a tool by name
    - List all tools
    - Expose tool manifests for discovery
    """

    def __init__(self):
        self.tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool using its manifest name.
        """
        self.tools[tool.manifest.name] = tool

    def get(self, name: str) -> BaseTool:
        """
        Retrieve a tool by name.
        """
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' is not registered.")

        return self.tools[name]

    def list_tools(self) -> list[str]:
        """
        Return a list of registered tool names.
        """
        return list(self.tools.keys())

    def discover(self) -> list[ToolManifest]:
        """
        Return the manifests of all registered tools.
        """
        return [tool.manifest for tool in self.tools.values()]
