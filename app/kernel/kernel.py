from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.runtime.events import event_bus
from app.runtime.permissions import permission_engine
from app.runtime.recorder import execution_recorder
from app.runtime.scheduler import resource_scheduler
from app.schemas.tool_result import ToolResult
from app.tools.loader import load_plugins, registry


def normalize_tool_result(result: ToolResult, *, tool_name: str) -> ToolResult:
    """Ensure failed results always carry a usable error string."""
    if result.success:
        return result
    error = (result.error or "").strip()
    if error:
        return result
    if result.output is not None and str(result.output).strip():
        error = str(result.output).strip()
    else:
        error = f"Tool '{tool_name}' failed without an error message."
    return result.model_copy(update={"error": error})


def validate_tool_arguments(tool_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    Drop unknown keys and require schema-required fields when a parameters schema exists.
    """
    tool = registry.get(tool_name)
    schema = getattr(tool.manifest, "parameters", None) or {}
    properties = schema.get("properties") if isinstance(schema, dict) else None
    required = schema.get("required") if isinstance(schema, dict) else None

    cleaned = dict(kwargs)
    if isinstance(properties, dict) and properties:
        allowed = set(properties.keys())
        cleaned = {key: value for key, value in cleaned.items() if key in allowed}

    missing: list[str] = []
    if isinstance(required, list):
        for key in required:
            if key not in cleaned or cleaned[key] is None:
                missing.append(str(key))
            elif isinstance(cleaned[key], str) and not cleaned[key].strip() and key != "content":
                # empty path/query etc. is invalid; content may be intentionally empty
                if key in {"path", "command", "query", "expression", "code", "action"}:
                    missing.append(str(key))

    if missing:
        raise ValueError(
            f"Tool '{tool_name}' missing required arguments: {', '.join(missing)}. "
            f"Got keys: {', '.join(sorted(cleaned.keys())) or '(none)'}."
        )
    return cleaned


class ExecutionKernel:
    """
    Central execution engine with permissions, scheduling, events, and recording.
    """

    def __init__(self, role: str | None = None):
        load_plugins()
        self.role = role or settings.DEFAULT_ROLE

    async def execute(self, tool_name: str, role: str | None = None, **kwargs):
        effective_role = role or self.role
        tool = registry.get(tool_name)
        required = list(getattr(tool.manifest, "permissions", []) or [])

        await event_bus.publish(
            "ToolSelected",
            {"tool": tool_name, "parameters": kwargs, "role": effective_role},
        )

        permission_engine.require(effective_role, required)

        try:
            cleaned = validate_tool_arguments(tool_name, kwargs)
        except ValueError as exc:
            return normalize_tool_result(
                ToolResult(success=False, error=str(exc)),
                tool_name=tool_name,
            )

        lease_id = str(uuid4())
        await event_bus.publish("ExecutionStarted", {"tool": tool_name, "lease_id": lease_id})
        lease = await resource_scheduler.acquire(
            lease_id,
            cpu=settings.SANDBOX_CPU_LIMIT,
            memory_mb=min(settings.SANDBOX_MEMORY_MB, 512),
            holder=tool_name,
        )

        start = time.perf_counter()
        result: ToolResult | None = None
        error = None
        try:
            try:
                raw = await tool.execute(**cleaned)
            except TypeError as exc:
                # Common when the model invents/omits argument names.
                raw = ToolResult(
                    success=False,
                    error=f"Invalid arguments for '{tool_name}': {exc}",
                    execution_time=time.perf_counter() - start,
                    metadata={"arguments": cleaned},
                )
            except Exception as exc:  # noqa: BLE001
                raw = ToolResult(
                    success=False,
                    error=str(exc) or f"Tool '{tool_name}' raised {type(exc).__name__}",
                    execution_time=time.perf_counter() - start,
                    metadata={"arguments": cleaned},
                )
            result = normalize_tool_result(raw, tool_name=tool_name)
            if not result.success:
                error = result.error
            return result
        finally:
            duration = time.perf_counter() - start
            await resource_scheduler.release(lease_id)
            execution_recorder.record(
                tool=tool_name,
                parameters=cleaned if "cleaned" in locals() else kwargs,
                output=None if result is None else result.output,
                error=error or (None if result is None else result.error),
                success=bool(result and result.success) and error is None,
                duration=duration,
                memory_mb=float(lease.memory_mb),
                cpu=lease.cpu,
            )
            await event_bus.publish(
                "ExecutionFinished",
                {
                    "tool": tool_name,
                    "success": bool(result and result.success) and error is None,
                    "duration": duration,
                    "error": error,
                },
            )
