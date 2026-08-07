from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from app.agents.errors import ChatCancelled
from app.core.config import settings
from app.core.logger import logger
from app.kernel.kernel import ExecutionKernel
from app.llm.base import StreamDelta
from app.llm.router import llm_router
from app.runtime.events import event_bus
from app.storage.db import storage
from app.storage.paths import paths
from app.tools.loader import load_plugins, registry


SYSTEM_PROMPT = """You are ForgeAI, a coding and operations agent with tools.

When a project folder is open, file/terminal/python tools run inside that project root.
Paths are relative to the project root (e.g. "README.md", "src/app.py"), never absolute host paths unless the user gave them.

## How to use tools
- Call tools via the function-calling API with the exact argument names in each tool schema.
- Prefer read_file / write_file / patch for file edits. Do NOT use terminal echo/heredoc/sed for edits.
- Use terminal for running commands (ls/dir, git, pytest, npm, etc.) within the allowlist.
- Use filesystem only for list/read/write convenience; prefer read_file/write_file/patch when editing code.
- After tool results arrive, continue: call more tools if needed, or give a clear final answer with NO tool call.
- If a tool fails, read the error, adjust arguments, and retry when useful.
- Do not invent tool names or argument keys that are not in the schemas.

## Style
- Be concise in the final answer.
- You may reason internally; keep the user-facing answer clear.
- You can see images attached to user messages when provided.
"""

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


class ChatLoop:
    """
    Hermes-style think -> tool -> observe loop embedded in chat sessions.
    """

    def __init__(self):
        load_plugins()
        self.kernel = ExecutionKernel()
        self._queues: dict[str, list[asyncio.Queue]] = {}
        self._cancel_flags: set[str] = set()

    def subscribe(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(session_id, []).append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        items = self._queues.get(session_id, [])
        if queue in items:
            items.remove(queue)

    def request_cancel(self, session_id: str) -> bool:
        """Ask the active loop for this session to stop after the current await."""
        self._cancel_flags.add(session_id)
        return True

    def _clear_cancel(self, session_id: str) -> None:
        self._cancel_flags.discard(session_id)

    def _raise_if_cancelled(self, session_id: str) -> None:
        if session_id in self._cancel_flags:
            raise ChatCancelled("Generation stopped by user.")

    async def _emit(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        body = {"session_id": session_id, **payload}
        await event_bus.publish(event_type, body)
        for queue in list(self._queues.get(session_id, [])):
            await queue.put({"type": event_type, "payload": body})

    def _tool_schemas(self) -> list[dict[str, Any]]:
        return [manifest.openai_tool() for manifest in registry.discover()]

    def _resolve_attachments(
        self,
        user_id: str,
        session_id: str,
        filenames: list[str] | None,
    ) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        uploads = paths.uploads_path(user_id, session_id)
        for raw_name in filenames or []:
            name = Path(raw_name).name
            target = (uploads / name).resolve()
            if not target.is_relative_to(uploads.resolve()) or not target.is_file():
                continue
            mime, _ = mimetypes.guess_type(name)
            kind = "image" if target.suffix.lower() in _IMAGE_SUFFIXES else "file"
            resolved.append(
                {
                    "name": name,
                    "kind": kind,
                    "mime": mime or "application/octet-stream",
                    "bytes": target.stat().st_size,
                    "path": str(target),
                }
            )
        return resolved

    def _image_b64(self, path: str) -> str | None:
        file_path = Path(path)
        if not file_path.is_file() or file_path.suffix.lower() not in _IMAGE_SUFFIXES:
            return None
        return base64.b64encode(file_path.read_bytes()).decode("ascii")

    def _history_as_messages(
        self,
        session_id: str,
        *,
        user_id: str,
    ) -> list[dict[str, Any]]:
        rows = storage.list_messages(session_id)
        messages: list[dict[str, Any]] = []
        for row in rows:
            role = row["role"]
            if role in {"user", "assistant", "system", "tool"}:
                item: dict[str, Any] = {"role": role, "content": row["content"]}
                meta = row.get("metadata") or {}
                if role == "tool" and meta.get("tool_call_id"):
                    item["tool_call_id"] = meta["tool_call_id"]
                    if meta.get("tool"):
                        item["name"] = meta["tool"]
                if role == "assistant" and meta.get("tool_calls"):
                    item["tool_calls"] = meta["tool_calls"]
                if role == "assistant" and meta.get("thinking"):
                    item["thinking"] = meta["thinking"]
                if role == "user":
                    images: list[Any] = []
                    missing_names: list[str] = []
                    for attachment in meta.get("attachments") or []:
                        if attachment.get("missing") or attachment.get("deleted"):
                            missing_names.append(attachment.get("name") or "file")
                            continue
                        if attachment.get("kind") != "image":
                            continue
                        path = attachment.get("path") or ""
                        encoded = self._image_b64(path)
                        if not encoded:
                            # Fall back to uploads folder by name
                            encoded = self._image_b64(
                                str(paths.uploads_path(user_id, session_id) / attachment["name"])
                            )
                            path = str(
                                paths.uploads_path(user_id, session_id) / attachment["name"]
                            )
                        if encoded:
                            mime = attachment.get("mime") or mimetypes.guess_type(path)[0]
                            if not mime or not str(mime).startswith("image/"):
                                suffix = Path(path or attachment.get("name") or "").suffix.lower()
                                mime = {
                                    ".png": "image/png",
                                    ".jpg": "image/jpeg",
                                    ".jpeg": "image/jpeg",
                                    ".gif": "image/gif",
                                    ".webp": "image/webp",
                                    ".bmp": "image/bmp",
                                }.get(suffix, "image/png")
                            images.append({"data": encoded, "mime": mime})
                        else:
                            missing_names.append(attachment.get("name") or "file")
                    if images:
                        item["images"] = images
                    # Keep prior chat text as memory; note missing binaries so the model
                    # does not invent that it can still see deleted files.
                    if missing_names:
                        note = (
                            "\n\n[Attachment unavailable — deleted from storage: "
                            + ", ".join(missing_names)
                            + "]"
                        )
                        item["content"] = f"{item.get('content') or ''}{note}"
                messages.append(item)
        return messages

    def _assistant_metadata(
        self,
        response,
        *,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta: dict[str, Any] = dict(extra or {})
        if getattr(response, "thinking", None):
            meta["thinking"] = response.thinking
        return meta

    async def run(
        self,
        *,
        user_id: str,
        session_id: str,
        content: str,
        role: str | None = None,
        max_steps: int | None = None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        session = storage.get_session(session_id)
        if not session or session["user_id"] != user_id:
            raise KeyError(f"Session '{session_id}' not found for user.")

        # Ensure workspace exists for tools
        paths.workspace_path(user_id, session_id)
        self.kernel.role = role or storage.get_user(user_id)["role"]

        text = (content or "").strip()
        resolved_attachments = self._resolve_attachments(user_id, session_id, attachments)
        if not text and not resolved_attachments:
            raise ValueError("Message content or attachments required.")

        needs_title = session["title"] in {"New chat", "New Chat"}

        user_meta: dict[str, Any] = {}
        if resolved_attachments:
            user_meta["attachments"] = [
                {
                    "name": item["name"],
                    "kind": item["kind"],
                    "mime": item["mime"],
                    "bytes": item["bytes"],
                    "path": item["path"],
                }
                for item in resolved_attachments
            ]

        storage.add_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=text or "(attachment)",
            metadata=user_meta or None,
        )
        await self._emit(
            session_id,
            "UserMessage",
            {"content": text or "(attachment)", "attachments": user_meta.get("attachments", [])},
        )

        max_steps = max_steps or settings.AGENT_MAX_STEPS
        tools = self._tool_schemas()
        final_text = ""
        steps = 0
        cancelled = False
        self._clear_cancel(session_id)

        try:
            for step in range(1, max_steps + 1):
                self._raise_if_cancelled(session_id)
                steps = step
                messages = self._history_as_messages(session_id, user_id=user_id)
                await self._emit(session_id, "ModelThinking", {"step": step})

                async def on_delta(delta: StreamDelta, *, _step: int = step) -> None:
                    self._raise_if_cancelled(session_id)
                    if delta.thinking:
                        await self._emit(
                            session_id,
                            "ThinkingDelta",
                            {"delta": delta.thinking, "step": _step},
                        )
                    if delta.content:
                        await self._emit(
                            session_id,
                            "ContentDelta",
                            {"delta": delta.content, "step": _step},
                        )

                try:
                    response = await llm_router.chat(
                        messages,
                        tools=tools,
                        system=SYSTEM_PROMPT,
                        on_delta=on_delta,
                    )
                except ChatCancelled:
                    raise
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
                        response = await self._heuristic_turn(text)

                self._raise_if_cancelled(session_id)

                storage.record_tokens(
                    user_id=user_id,
                    session_id=session_id,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                )

                if response.thinking:
                    await self._emit(
                        session_id,
                        "AssistantThinking",
                        {"step": step, "thinking": response.thinking},
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
                        metadata=self._assistant_metadata(
                            response,
                            extra={"tool_calls": openai_tool_calls},
                        ),
                    )
                    await self._emit(
                        session_id,
                        "ToolCalls",
                        {
                            "step": step,
                            "tool_calls": response.tool_calls,
                            "thinking": response.thinking,
                        },
                    )

                    for call in response.tool_calls:
                        self._raise_if_cancelled(session_id)
                        tool_name = call["name"]
                        arguments = call.get("arguments") or {}
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
                        exec_kwargs = {
                            key: value
                            for key, value in arguments.items()
                            if not key.startswith("_")
                        }
                        from app.tools.context import session_context_scope

                        # Use context manager for proper async-safe context isolation
                        async with session_context_scope(
                            user_id=user_id,
                            session_id=session_id,
                            project_root=session.get("project_root"),
                        ):
                            result = await self.kernel.execute(tool_name, **exec_kwargs)

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
                    metadata=self._assistant_metadata(response),
                )
                await self._emit(
                    session_id,
                    "AssistantMessage",
                    {
                        "content": final_text,
                        "thinking": response.thinking,
                        "step": step,
                    },
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
        except ChatCancelled:
            cancelled = True
            final_text = (final_text or "").strip() or "Generation stopped."
            storage.add_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=final_text,
                metadata={"stopped": "cancelled"},
            )
            await self._emit(
                session_id,
                "ChatCancelled",
                {"content": final_text, "steps": steps},
            )
        finally:
            self._clear_cancel(session_id)

        if needs_title and final_text and not cancelled:
            await self._summarize_session_title(
                session_id=session_id,
                user_text=text or "(attachment)",
                assistant_text=final_text,
            )

        await self._emit(
            session_id,
            "ChatCompleted",
            {"content": final_text, "steps": steps, "cancelled": cancelled},
        )
        storage.audit(
            "chat.completed" if not cancelled else "chat.cancelled",
            {"session_id": session_id, "user_id": user_id, "steps": steps},
        )
        return {
            "session_id": session_id,
            "content": final_text,
            "steps": steps,
            "cancelled": cancelled,
            "stats": storage.session_stats(session_id),
            "messages": storage.list_messages(session_id),
        }

    async def _summarize_session_title(
        self,
        *,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Set sidebar title after the first assistant reply (user + answer context)."""
        try:
            raw = await llm_router.complete(
                prompt=(
                    "Create a short chat sidebar title (3-7 words) for this conversation. "
                    "No quotes, no trailing punctuation, no markdown.\n\n"
                    f"User:\n{(user_text or '').strip()[:400]}\n\n"
                    f"Assistant:\n{(assistant_text or '').strip()[:400]}"
                ),
                system="You name chat sessions. Reply with only the title text.",
            )
            title = " ".join((raw or "").strip().split())[:60]
            if not title:
                title = " ".join((user_text or "Chat").split())[:48] or "Chat"
            storage.touch_session(session_id, title=title)
            await self._emit(session_id, "SessionTitle", {"title": title})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Session title summary failed: %s", exc)
            fallback = " ".join((user_text or "Chat").split())[:48] or "Chat"
            storage.touch_session(session_id, title=fallback)
            await self._emit(session_id, "SessionTitle", {"title": fallback})

    async def _heuristic_turn(self, text: str):
        from app.llm.base import LLMResponse
        from app.tools.selector import ToolSelector

        selector = ToolSelector()
        tool = selector.select(text)
        if tool is None:
            return LLMResponse(content=f"(no LLM configured) Echo: {text}")
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
