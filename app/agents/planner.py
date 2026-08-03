import re

from app.agents.base import BaseAgent
from app.kernel.kernel import ExecutionKernel
from app.schemas.tool_result import ToolResult
from app.tools.loader import load_plugins
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
        load_plugins()
        self.kernel = ExecutionKernel()
        self.selector = ToolSelector()

    async def run(self, user_input: str) -> ToolResult:
        tool = self.selector.select(user_input)

        if tool is None:
            return ToolResult(
                success=False,
                error="No suitable tool found.",
            )

        arguments = self._build_arguments(
            tool.manifest.name,
            user_input,
        )

        return await self.kernel.execute(
            tool_name=tool.manifest.name,
            **arguments,
        )

    def _build_arguments(
        self,
        tool_name: str,
        user_input: str,
    ) -> dict:
        if tool_name == "calculator":
            return {"expression": self._extract_calculator_expression(user_input)}

        if tool_name == "python":
            return {"code": self._extract_python_code(user_input)}

        if tool_name == "terminal":
            return {"command": self._extract_terminal_command(user_input)}

        if tool_name == "filesystem":
            return self._build_filesystem_arguments(user_input)

        return {}

    def _extract_calculator_expression(self, user_input: str) -> str:
        text = user_input.strip()
        lowered = text.lower()
        for prefix in (
            "calculate",
            "compute",
            "evaluate",
            "math",
            "equation",
            "expression",
        ):
            if lowered.startswith(prefix):
                return text[len(prefix):].strip(" :")
        return text

    def _extract_python_code(self, user_input: str) -> str:
        fenced = re.search(r"```(?:python)?\s*(.*?)```", user_input, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()

        lowered = user_input.lower()
        for prefix in ("run python", "execute python", "python"):
            if lowered.startswith(prefix):
                return user_input[len(prefix):].strip(" :")

        return user_input.strip()

    def _extract_terminal_command(self, user_input: str) -> str:
        lowered = user_input.lower()
        for prefix in ("run command", "run shell", "terminal", "shell", "run"):
            if lowered.startswith(prefix):
                return user_input[len(prefix):].strip(" :")

        return user_input.strip()

    def _build_filesystem_arguments(self, user_input: str) -> dict:
        text = user_input.strip()
        lowered = text.lower()

        write_match = re.search(
            r"write\s+(?:to\s+)?(?P<path>\S+)\s+(?:with\s+|content\s+)?(?P<content>.+)$",
            text,
            re.IGNORECASE,
        )
        if write_match or "write" in lowered:
            if write_match:
                return {
                    "action": "write",
                    "path": write_match.group("path").strip("\"'"),
                    "content": write_match.group("content").strip(),
                }
            return {"action": "write", "path": ".", "content": text}

        read_match = re.search(
            r"read\s+(?:file\s+)?(?P<path>\S+)",
            text,
            re.IGNORECASE,
        )
        if read_match or "read" in lowered:
            path = read_match.group("path").strip("\"'") if read_match else "."
            return {"action": "read", "path": path}

        list_match = re.search(
            r"list\s+(?:files?\s+(?:in\s+|from\s+)?|directory\s+|folder\s+)?(?P<path>\S+)?",
            text,
            re.IGNORECASE,
        )
        if list_match or "list" in lowered or "directory" in lowered or "folder" in lowered:
            path = "."
            if list_match and list_match.group("path"):
                path = list_match.group("path").strip("\"'")
            return {"action": "list", "path": path}

        return {"action": "list", "path": "."}
