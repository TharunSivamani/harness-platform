from app.tools.loader import registry


class ExecutionKernel:
    """
    Central execution engine for all tools.
    """

    async def execute(self, tool_name: str, **kwargs):
        tool = registry.get(tool_name)

        return await tool.execute(**kwargs)