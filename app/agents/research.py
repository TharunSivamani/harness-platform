from app.agents.base import BaseAgent
from app.kernel.kernel import ExecutionKernel
from app.schemas.tool_result import ToolResult
from app.tools.loader import load_plugins


class ResearchAgent(BaseAgent):
    """
    Research-focused agent that prefers search / browser tools.
    """

    def __init__(self):
        load_plugins()
        self.kernel = ExecutionKernel()

    async def run(self, user_input: str) -> ToolResult:
        query = user_input.strip()
        lowered = query.lower()
        for prefix in ("research", "investigate", "look up"):
            if lowered.startswith(prefix):
                query = query[len(prefix) :].strip(" :")
                break

        return await self.kernel.execute("search", query=query, max_results=5)
