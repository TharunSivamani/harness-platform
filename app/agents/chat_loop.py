from __future__ import annotations

import asyncio
import json
from typing import Any

from app.core.config import settings
from app.core.logger import logger
from app.kernel.kernel import ExecutionKernel
from app.llm.router import llm_router
from app.runtime.events import event_bus
from app.storage.db import storage
from app.storage.paths import paths
from app.tools.loader import load_plugins, registry


SYSTEM_PROMPT = """You are ForgeAI, a helpful coding and operations agent.
Use tools when they improve correctness. Prefer read_file/write_file/patch over shell for file edits.
Prefer terminal for running commands. When finished, respond with a clear final answer and no tool call.
"""


class ChatLoop:
    """
    Hermes-style think -> tool -> observe loop embedded in chat sessions.
    """

    def __init__(self):
        load_plugins()
        self.kernel = ExecutionKernel()
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(session_id, []).append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        items = self._queues.get(session_id, [])
        if queue in items:
            items.remove(queue)

    async def _emit(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        body = {"session_id": session_id, **payload}
        await event_bus.publish(event_type, body)
        for queue in list(self._queues.get(session_id, [])):
            await queue.put({"type": event_type, "payload": body})

    def _tool_schemas(self) -> list[dict[str, Any]]:
        tools = []
        for manifest in registry.discover():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": manifest.name,
                        "description": manifest.description,
                        "parameters": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                }
            )
        return tools

    def _history_as_messages(self, session_id: str) -> list[dict[str, Any]]:
        rows = storage.list_messages(session_id)
        messages: list[dict[str, Any]] = []
        for row in rows:
            role = row["role"]
            if role in {"user", "assistant", "system", "tool"}:
                item: dict[str, Any] = {"role": role, "content": row["content"]}
                meta = row.get("metadata") or {}
                if role == "tool" and meta.get("tool_call_id"):
                    item["tool_call_id"] = meta["tool_call_id"]
                if role == "assistant" and meta.get("tool_calls"):
                    item["tool_calls"] = meta["tool_calls"]
                messages.append(item)
        return messages

    async def run(
        self,
        *,
        user_id: str,
        session_id: str,
        content: str,
        role: str | None = None,
        max_steps: int | None = None,
    ) -> dict[str, Any]:
        session = storage.get_session(session_id)
        if not session or session["user_id"] != user_id:
            raise KeyError(f"Session '{session_id}' not found for user.")

        # Ensure workspace exists for tools
        paths.workspace_path(user_id, session_id)
        self.kernel.role = role or storage.get_user(user_id)["role"]

        if session["title"] in {"New chat", "New Chat"} and content.strip():
            title = content.strip()[:48]
            storage.touch_session(session_id, title=title)

        storage.add_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=content,
        )
        await self._emit(session_id, "UserMessage", {"content": content})

        max_steps = max_steps or settings.AGENT_MAX_STEPS
        tools = self._tool_schemas()
        final_text = ""
        steps = 0

        for step in range(1, max_steps + 1):
            steps = step
            messages = self._history_as_messages(session_id)
            await self._emit(session_id, "ModelThinking", {"step": step})

            try:
                response = await llm_router.chat(
                    messages,
                    tools=tools,
                    system=SYSTEM_PROMPT,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM chat failed, heuristic fallback: %s", exc)
                if step > 1:
                    last_tool = next(
                        (m for m in reversed(messages) if m.get("role") == "tool"),
                        None,
                    )
                    from app.llm.base import LLMResponse

                    response = LLMResponse(
                        content=last_tool["content"] if last_tool else "Completed tool steps."
                    )
                else:
                    response = await self._heuristic_turn(content)

            storage.record_tokens(
                user_id=user_id,
                session_id=session_id,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )

            if response.tool_calls:
                openai_tool_calls = []
                for call in response.tool_calls:
                    openai_tool_calls.append(
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(call.get("arguments") or {}),
                            },
                        }
                    )
                storage.add_message(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content=response.content or "",
                    metadata={"tool_calls": openai_tool_calls},
                )
                await self._emit(
                    session_id,
                    "ToolCalls",
                    {"step": step, "tool_calls": response.tool_calls},
                )

                for call in response.tool_calls:
                    tool_name = call["name"]
                    arguments = call.get("arguments") or {}
                    # Inject session workspace for path-aware tools
                    if tool_name in {
                        "terminal",
                        "read_file",
                        "write_file",
                        "patch",
                        "filesystem",
                        "python",
                    }:
                        arguments = {
                            **arguments,
                            "_user_id": user_id,
                            "_session_id": session_id,
                        }

                    await self._emit(
                        session_id,
                        "ToolStarted",
                        {"tool": tool_name, "arguments": arguments, "step": step},
                    )
                    # Strip internal kwargs before execute if tool doesn't accept them
                    exec_kwargs = {
                        key: value
                        for key, value in arguments.items()
                        if not key.startswith("_")
                    }
                    # Set process-local context for file tools
                    from app.tools import context as tool_context

                    tool_context.set_session(user_id, session_id)
                    try:
                        result = await self.kernel.execute(tool_name, **exec_kwargs)
                    finally:
                        tool_context.clear_session()

                    result_payload = result.model_dump()
                    storage.add_message(
                        session_id=session_id,
                        user_id=user_id,
                        role="tool",
                        content=json.dumps(result_payload, default=str)[:8000],
                        metadata={
                            "tool_call_id": call["id"],
                            "tool": tool_name,
                            "success": result.success,
                        },
                    )
                    await self._emit(
                        session_id,
                        "ToolFinished",
                        {
                            "tool": tool_name,
                            "success": result.success,
                            "output": result.output,
                            "error": result.error,
                            "step": step,
                        },
                    )
                continue

            final_text = (response.content or "").strip() or "Done."
            storage.add_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=final_text,
            )
            await self._emit(
                session_id,
                "AssistantMessage",
                {"content": final_text, "step": step},
            )
            break
        else:
            final_text = final_text or "Stopped after max tool steps."
            storage.add_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=final_text,
                metadata={"stopped": "max_steps"},
            )

        await self._emit(
            session_id,
            "ChatCompleted",
            {"content": final_text, "steps": steps},
        )
        storage.audit(
            "chat.completed",
            {"session_id": session_id, "user_id": user_id, "steps": steps},
        )
        return {
            "session_id": session_id,
            "content": final_text,
            "steps": steps,
            "stats": storage.session_stats(session_id),
            "messages": storage.list_messages(session_id),
        }

    async def _heuristic_turn(self, text: str):
        from app.llm.base import LLMResponse
        from app.tools.selector import ToolSelector

        selector = ToolSelector()
        tool = selector.select(text)
        if tool is None:
            return LLMResponse(content=f"(no LLM configured) Echo: {text}")
        # Ask model-equivalent: one tool then done on next loop via tool result
        args: dict[str, Any] = {}
        name = tool.manifest.name
        if name == "calculator":
            args = {"expression": text.replace("calculate", "").strip()}
        elif name == "python":
            args = {"code": text}
        elif name == "search":
            args = {"query": text, "max_results": 3}
        elif name == "terminal":
            args = {"command": text.replace("run", "", 1).strip()}
        elif name in {"read_file", "filesystem"}:
            args = {"path": "."} if name == "read_file" else {"action": "list", "path": "."}
        return LLMResponse(
            content=None,
            tool_calls=[{"id": "heuristic-1", "name": name, "arguments": args}],
        )


chat_loop = ChatLoop()
