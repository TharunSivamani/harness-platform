from app.agents.base import BaseAgent
from app.kernel.kernel import ExecutionKernel
from app.schemas.tool_result import ToolResult
from app.tools.loader import load_plugins


class ExecutorAgent(BaseAgent):
    """
    Executes an explicit tool invocation: tool_name: args...
    """

    def __init__(self):
        load_plugins()
        self.kernel = ExecutionKernel()

    async def run(self, user_input: str) -> ToolResult:
        text = user_input.strip()
        if ":" not in text:
            return ToolResult(
                success=False,
                error="Executor expects format 'tool_name: argument'",
            )

        tool_name, remainder = text.split(":", 1)
        tool_name = tool_name.strip()
        argument = remainder.strip()

        if tool_name == "calculator":
            return await self.kernel.execute(tool_name, expression=argument)
        if tool_name == "python":
            return await self.kernel.execute(tool_name, code=argument)
        if tool_name == "terminal":
            return await self.kernel.execute(tool_name, command=argument)
        if tool_name == "search":
            return await self.kernel.execute(tool_name, query=argument)

        return await self.kernel.execute(tool_name)
