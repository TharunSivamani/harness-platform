from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.core.logger import logger
from app.kernel.kernel import ExecutionKernel
from app.llm.router import llm_router
from app.memory.session import session_manager
from app.runtime.events import event_bus
from app.runtime.state import TaskState, state_machine
from app.runtime.workspace import workspace_manager
from app.tools.loader import load_plugins, registry
from app.tools.selector import ToolSelector


@dataclass
class AgentStep:
    step: int
    thought: str
    action: str
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    status: str = "pending"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class AgentRun:
    run_id: str
    goal: str
    status: str = "running"
    session_id: str | None = None
    workspace_id: str | None = None
    steps: list[AgentStep] = field(default_factory=list)
    final_output: Any = None
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AgentRunner:
    """
    Multi-step autonomous agent harness.

    Loop:
      plan -> (optional approval) -> execute tool -> append result -> repeat
      until final answer, max steps, failure, or pause.
    """

    def __init__(self):
        load_plugins()
        self.kernel = ExecutionKernel()
        self.selector = ToolSelector()
        self._runs: dict[str, AgentRun] = {}
        self._queues: dict[str, list[asyncio.Queue]] = {}
        self._approvals: dict[str, asyncio.Event] = {}

    def get(self, run_id: str) -> AgentRun:
        if run_id not in self._runs:
            raise KeyError(f"Run '{run_id}' not found.")
        return self._runs[run_id]

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._queues.get(run_id, [])
        if queue in subscribers:
            subscribers.remove(queue)

    async def _emit(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        body = {"run_id": run_id, **payload}
        await event_bus.publish(event_type, body)
        for queue in list(self._queues.get(run_id, [])):
            await queue.put({"type": event_type, "payload": body})

    async def approve(self, run_id: str) -> None:
        event = self._approvals.get(run_id)
        if event:
            event.set()
            run = self.get(run_id)
            run.status = "running"
            run.updated_at = datetime.now(timezone.utc).isoformat()
            await self._emit(run_id, "RunApproved", {})

    async def start(
        self,
        goal: str,
        *,
        session_id: str | None = None,
        max_steps: int | None = None,
        role: str | None = None,
        auto_approve: bool | None = None,
    ) -> AgentRun:
        run_id = str(uuid4())
        workspace = workspace_manager.get_or_create(session_id)
        if session_id:
            session_manager.get_or_create(session_id)
            session_manager.add_message(session_id, "user", goal)

        run = AgentRun(
            run_id=run_id,
            goal=goal,
            session_id=session_id,
            workspace_id=workspace.workspace_id,
        )
        self._runs[run_id] = run

        task = state_machine.create(goal)
        state_machine.transition(task.task_id, TaskState.PLANNING)
        state_machine.transition(task.task_id, TaskState.RUNNING)

        asyncio.create_task(
            self._loop(
                run=run,
                task_id=task.task_id,
                max_steps=max_steps or settings.AGENT_MAX_STEPS,
                role=role or settings.DEFAULT_ROLE,
                auto_approve=(
                    settings.AGENT_AUTO_APPROVE
                    if auto_approve is None
                    else auto_approve
                ),
            )
        )
        return run

    async def _loop(
        self,
        *,
        run: AgentRun,
        task_id: str,
        max_steps: int,
        role: str,
        auto_approve: bool,
    ) -> None:
        await self._emit(run.run_id, "RunStarted", {"goal": run.goal})
        transcript: list[dict[str, Any]] = [{"role": "user", "content": run.goal}]

        try:
            for step_no in range(1, max_steps + 1):
                decision = await self._decide(run.goal, transcript, step_no)
                step = AgentStep(
                    step=step_no,
                    thought=decision.get("thought", ""),
                    action=decision.get("action", "final"),
                    tool=decision.get("tool"),
                    arguments=decision.get("arguments") or {},
                    status="planned",
                )
                run.steps.append(step)
                run.updated_at = datetime.now(timezone.utc).isoformat()

                await self._emit(
                    run.run_id,
                    "StepPlanned",
                    {
                        "step": step_no,
                        "thought": step.thought,
                        "action": step.action,
                        "tool": step.tool,
                        "arguments": step.arguments,
                    },
                )

                if step.action == "final" or not step.tool:
                    step.status = "completed"
                    run.final_output = decision.get("output") or step.thought or "Done."
                    run.status = "completed"
                    state_machine.transition(
                        task_id,
                        TaskState.COMPLETED,
                        output=run.final_output,
                    )
                    await self._emit(
                        run.run_id,
                        "RunCompleted",
                        {"output": run.final_output, "steps": step_no},
                    )
                    if run.session_id:
                        session_manager.add_message(
                            run.session_id,
                            "assistant",
                            str(run.final_output),
                        )
                    return

                if (
                    not auto_approve
                    and step.tool in settings.agent_approval_tools
                ):
                    step.status = "awaiting_approval"
                    run.status = "awaiting_approval"
                    state_machine.transition(task_id, TaskState.WAITING)
                    approval = asyncio.Event()
                    self._approvals[run.run_id] = approval
                    await self._emit(
                        run.run_id,
                        "ApprovalRequired",
                        {"step": step_no, "tool": step.tool, "arguments": step.arguments},
                    )
                    await approval.wait()
                    self._approvals.pop(run.run_id, None)
                    state_machine.transition(task_id, TaskState.RUNNING)
                    run.status = "running"

                step.status = "running"
                await self._emit(
                    run.run_id,
                    "ToolStarted",
                    {"step": step_no, "tool": step.tool, "arguments": step.arguments},
                )

                result = await self.kernel.execute(
                    step.tool,
                    role=role,
                    **step.arguments,
                )
                step.result = result.model_dump()
                step.status = "completed" if result.success else "failed"
                run.updated_at = datetime.now(timezone.utc).isoformat()

                await self._emit(
                    run.run_id,
                    "ToolFinished",
                    {
                        "step": step_no,
                        "tool": step.tool,
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                    },
                )

                transcript.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "thought": step.thought,
                                "tool": step.tool,
                                "arguments": step.arguments,
                            }
                        ),
                    }
                )
                transcript.append(
                    {
                        "role": "tool",
                        "content": json.dumps(step.result, default=str)[:4000],
                    }
                )

                if not result.success:
                    run.status = "failed"
                    run.error = result.error
                    state_machine.transition(
                        task_id,
                        TaskState.FAILED,
                        error=result.error,
                    )
                    await self._emit(
                        run.run_id,
                        "RunFailed",
                        {"error": result.error, "step": step_no},
                    )
                    return

            run.status = "failed"
            run.error = f"Reached max steps ({max_steps}) without final answer."
            state_machine.transition(task_id, TaskState.FAILED, error=run.error)
            await self._emit(run.run_id, "RunFailed", {"error": run.error})

        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent run failed")
            run.status = "failed"
            run.error = str(exc)
            try:
                state_machine.transition(task_id, TaskState.FAILED, error=str(exc))
            except Exception:  # noqa: BLE001
                pass
            await self._emit(run.run_id, "RunFailed", {"error": str(exc)})

    async def _decide(
        self,
        goal: str,
        transcript: list[dict[str, Any]],
        step_no: int,
    ) -> dict[str, Any]:
        if self._llm_available():
            try:
                return await self._decide_with_llm(goal, transcript, step_no)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM decide failed, using heuristic: %s", exc)
        return self._decide_heuristic(goal, transcript, step_no)

    def _llm_available(self) -> bool:
        provider = settings.LLM_PROVIDER.lower().strip()
        if provider == "openai":
            return bool(settings.get_openai_api_key())
        if provider == "anthropic":
            return bool(settings.get_anthropic_api_key())
        return provider in {"ollama", "vllm"}

    async def _decide_with_llm(
        self,
        goal: str,
        transcript: list[dict[str, Any]],
        step_no: int,
    ) -> dict[str, Any]:
        tools = registry.discover()
        tool_lines = [
            f"- {item.name}: {item.description} | perms={item.permissions}"
            for item in tools
        ]
        system = (
            "You are ForgeAI's autonomous agent controller. "
            "Decide the next action. Respond with JSON only: "
            '{"thought":"...","action":"tool"|"final","tool":"<name>|null,'
            '"arguments":{},"output":"<final answer if action=final>"}'
        )
        prompt = (
            f"Goal:\n{goal}\n\nStep: {step_no}\n\nTools:\n"
            + "\n".join(tool_lines)
            + "\n\nTranscript:\n"
            + json.dumps(transcript[-12:], indent=2, default=str)
        )
        raw = await llm_router.complete(prompt=prompt, system=system)
        return self._parse_json(raw)

    def _decide_heuristic(
        self,
        goal: str,
        transcript: list[dict[str, Any]],
        step_no: int,
    ) -> dict[str, Any]:
        tool_results = [item for item in transcript if item.get("role") == "tool"]

        if tool_results:
            last = tool_results[-1]["content"]
            return {
                "thought": "Tool finished; returning result to the user.",
                "action": "final",
                "tool": None,
                "arguments": {},
                "output": last,
            }

        tool = self.selector.select(goal)
        if tool is None:
            return {
                "thought": "No tool matched; answering directly.",
                "action": "final",
                "tool": None,
                "arguments": {},
                "output": f"I could not map the goal to a tool: {goal}",
            }

        arguments = self._build_arguments(tool.manifest.name, goal)
        return {
            "thought": f"Using {tool.manifest.name} for the goal.",
            "action": "tool",
            "tool": tool.manifest.name,
            "arguments": arguments,
        }

    def _build_arguments(self, tool_name: str, goal: str) -> dict[str, Any]:
        text = goal.strip()
        lowered = text.lower()

        if tool_name == "calculator":
            for prefix in ("calculate", "compute", "math"):
                if lowered.startswith(prefix):
                    return {"expression": text[len(prefix):].strip(" :")}
            return {"expression": text}

        if tool_name == "python":
            for prefix in ("run python", "python"):
                if lowered.startswith(prefix):
                    return {"code": text[len(prefix):].strip(" :")}
            return {"code": text}

        if tool_name == "terminal":
            for prefix in ("run", "terminal", "shell"):
                if lowered.startswith(prefix):
                    return {"command": text[len(prefix):].strip(" :")}
            return {"command": text}

        if tool_name == "search":
            for prefix in ("search for", "search", "research"):
                if lowered.startswith(prefix):
                    return {"query": text[len(prefix):].strip(" :"), "max_results": 3}
            return {"query": text, "max_results": 3}

        if tool_name == "filesystem":
            if "list" in lowered:
                return {"action": "list", "path": "."}
            if "read" in lowered:
                return {"action": "read", "path": "."}
            return {"action": "list", "path": "."}

        return {}

    def _parse_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise
            data = json.loads(match.group(0))
        if not isinstance(data, dict):
            raise ValueError("Decision JSON must be an object.")
        return data

    def serialize(self, run: AgentRun) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "goal": run.goal,
            "status": run.status,
            "session_id": run.session_id,
            "workspace_id": run.workspace_id,
            "final_output": run.final_output,
            "error": run.error,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "steps": [asdict(step) for step in run.steps],
        }


agent_runner = AgentRunner()
