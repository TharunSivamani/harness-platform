from app.tools.loader import load_plugins, registry


class ExecutionKernel:
    """
    Central execution engine for all tools.
    """

    def __init__(self):
        load_plugins()

    async def execute(self, tool_name: str, **kwargs):
        tool = registry.get(tool_name)

        return await tool.execute(**kwargs)