from app.agents.base import BaseAgent
from app.kernel.kernel import ExecutionKernel
from app.schemas.tool_result import ToolResult
from app.tools.loader import load_plugins


class CodingAgent(BaseAgent):
    """
    Coding-focused agent that prefers python / filesystem / terminal.
    """

    def __init__(self):
        load_plugins()
        self.kernel = ExecutionKernel()

    async def run(self, user_input: str) -> ToolResult:
        text = user_input.strip()
        lowered = text.lower()

        if "write" in lowered and "file" in lowered:
            return await self.kernel.execute(
                "filesystem",
                action="write",
                path="code_output.py",
                content=text,
            )

        code = text
        for prefix in ("code", "python", "run python"):
            if lowered.startswith(prefix):
                code = text[len(prefix) :].strip(" :")
                break

        return await self.kernel.execute("python", code=code)
