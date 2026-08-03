from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.runtime.events import event_bus
from app.runtime.permissions import permission_engine
from app.runtime.recorder import execution_recorder
from app.runtime.scheduler import resource_scheduler
from app.tools.loader import load_plugins, registry


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

        lease_id = str(uuid4())
        await event_bus.publish("ExecutionStarted", {"tool": tool_name, "lease_id": lease_id})
        lease = await resource_scheduler.acquire(
            lease_id,
            cpu=settings.SANDBOX_CPU_LIMIT,
            memory_mb=min(settings.SANDBOX_MEMORY_MB, 512),
            holder=tool_name,
        )

        start = time.perf_counter()
        result = None
        error = None
        try:
            result = await tool.execute(**kwargs)
            return result
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            raise
        finally:
            duration = time.perf_counter() - start
            await resource_scheduler.release(lease_id)
            execution_recorder.record(
                tool=tool_name,
                parameters=kwargs,
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
                },
            )
