from app.agents.coding import CodingAgent
from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.research import ResearchAgent
from app.agents.reviewer import ReviewerAgent
from app.schemas.tool_result import ToolResult


class MultiAgentOrchestrator:
    """
    Routes requests to specialized agents, then reviews the result.
    """

    def __init__(self):
        self.planner = PlannerAgent()
        self.research = ResearchAgent()
        self.coding = CodingAgent()
        self.executor = ExecutorAgent()
        self.reviewer = ReviewerAgent()

    def _select_agent(self, user_input: str):
        text = user_input.lower()
        if text.startswith("execute ") or ":" in user_input.split(" ", 1)[0]:
            return "executor", self.executor
        if any(token in text for token in ("research", "search", "lookup", "investigate")):
            return "research", self.research
        if any(token in text for token in ("code", "python", "write file", "implement")):
            return "coding", self.coding
        return "planner", self.planner

    async def run(self, user_input: str) -> ToolResult:
        agent_name, agent = self._select_agent(user_input)
        result = await agent.run(user_input)

        review_payload = str(result.output if result.success else result.error)
        review = await self.reviewer.run(review_payload)

        return ToolResult(
            success=result.success,
            output={
                "agent": agent_name,
                "result": result.model_dump(),
                "review": review.model_dump(),
            },
            error=result.error,
            execution_time=result.execution_time,
            metadata={"orchestrator": "multi-agent"},
        )
