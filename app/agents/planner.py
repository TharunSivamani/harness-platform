import json
import re

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.logger import logger
from app.kernel.kernel import ExecutionKernel
from app.llm.router import llm_router
from app.schemas.tool_result import ToolResult
from app.tools.loader import load_plugins, registry
from app.tools.selector import ToolSelector


class PlannerAgent(BaseAgent):
    """
    Planner Agent

    Responsibilities:
    1. Receive user input.
    2. Select the best tool (LLM or keyword fallback).
    3. Execute the tool through the kernel.
    4. Return the ToolResult.
    """

    def __init__(self):
        load_plugins()
        self.kernel = ExecutionKernel()
        self.selector = ToolSelector()

    async def run(self, user_input: str) -> ToolResult:
        plan = None

        if self._should_use_llm():
            try:
                plan = await self._plan_with_llm(user_input)
            except Exception as exc:
                logger.warning("LLM planning failed, falling back to keywords: %s", exc)

        if plan is None:
            tool = self.selector.select(user_input)
            if tool is None:
                return ToolResult(
                    success=False,
                    error="No suitable tool found.",
                )
            plan = {
                "tool": tool.manifest.name,
                "arguments": self._build_arguments(tool.manifest.name, user_input),
            }

        return await self.kernel.execute(
            tool_name=plan["tool"],
            **plan.get("arguments", {}),
        )

    def _should_use_llm(self) -> bool:
        mode = settings.PLANNER_MODE.lower().strip()
        if mode == "keyword":
            return False
        if mode == "llm":
            return True

        provider = settings.LLM_PROVIDER.lower().strip()
        if provider == "openai":
            return bool(settings.get_openai_api_key())
        if provider == "anthropic":
            return bool(settings.get_anthropic_api_key())
        if provider in {"ollama", "vllm"}:
            return True
        return False

    async def _plan_with_llm(self, user_input: str) -> dict:
        manifests = registry.discover()
        tool_lines = []
        for manifest in manifests:
            params = json.dumps(manifest.parameters or {}, separators=(",", ":"))
            tool_lines.append(
                f"- {manifest.name}: {manifest.description}\n"
                f"  parameters schema: {params}"
            )

        system = (
            "You are the ForgeAI planner. Choose exactly one tool and arguments. "
            "Use only argument keys from that tool's parameters schema. "
            "Respond with JSON only in this shape: "
            '{"tool": "<name>", "arguments": {}}. '
            "Do not include markdown."
        )
        prompt = (
            "Available tools:\n"
            + "\n".join(tool_lines)
            + "\n\nUser request:\n"
            + user_input
        )

        llm = llm_router
        raw = await llm.complete(prompt=prompt, system=system)
        data = self._parse_llm_json(raw)

        tool_name = data.get("tool")
        arguments = data.get("arguments") or {}

        if not tool_name or tool_name not in registry.list_tools():
            raise ValueError(f"LLM selected unknown tool: {tool_name}")

        if not isinstance(arguments, dict):
            raise ValueError("LLM arguments must be an object.")

        return {"tool": tool_name, "arguments": arguments}

    def _parse_llm_json(self, raw: str) -> dict:
        text = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

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

        if tool_name == "search":
            return {"query": self._extract_search_query(user_input)}

        if tool_name == "browser":
            return self._build_browser_arguments(user_input)

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

    def _extract_search_query(self, user_input: str) -> str:
        text = user_input.strip()
        lowered = text.lower()
        for prefix in (
            "search for",
            "search",
            "lookup",
            "find",
            "google",
            "web search",
        ):
            if lowered.startswith(prefix):
                return text[len(prefix):].strip(" :")
        return text

    def _build_browser_arguments(self, user_input: str) -> dict:
        text = user_input.strip()
        lowered = text.lower()

        url_match = re.search(r"https?://\S+", text)
        url = url_match.group(0).rstrip(".,)") if url_match else None

        if "screenshot" in lowered:
            path_match = re.search(
                r"screenshot(?:\s+to)?\s+(?P<path>\S+\.png)",
                text,
                re.I,
            )
            return {
                "action": "screenshot",
                "url": url,
                "path": path_match.group("path") if path_match else "screenshot.png",
            }

        if "content" in lowered or "extract" in lowered or "text" in lowered:
            return {"action": "content", "url": url}

        return {"action": "navigate", "url": url}
