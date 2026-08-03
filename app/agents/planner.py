from app.agents.base import BaseAgent
from app.kernel.kernel import ExecutionKernel
from app.schemas.tool_result import ToolResult
from app.tools.selector import ToolSelector


class PlannerAgent(BaseAgent):
    """
    Planner Agent

    Responsibilities:
    1. Receive user input.
    2. Select the best tool.
    3. Execute the tool through the kernel.
    4. Return the ToolResult.
    """

    def __init__(self):
        self.kernel = ExecutionKernel()
        self.selector = ToolSelector()

    async def run(self, user_input: str) -> ToolResult:
        """
        Main entry point for the planner.
        """

        # Select the most appropriate tool
        tool = self.selector.select(user_input)

        if tool is None:
            return ToolResult(
                success=False,
                error="No suitable tool found.",
            )

        # Build arguments based on the selected tool
        arguments = self._build_arguments(
            tool.manifest.name,
            user_input,
        )

        # Execute through the kernel
        return await self.kernel.execute(
            tool_name=tool.manifest.name,
            **arguments,
        )

    def _build_arguments(
        self,
        tool_name: str,
        user_input: str,
    ) -> dict:
        """
        Converts raw user input into the arguments
        expected by each tool.

        For now, only the calculator tool is supported.
        """

        if tool_name == "calculator":
            return {
                "expression": user_input
            }

        return {}