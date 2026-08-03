from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings


@dataclass
class ExecutionRecord:
    record_id: str
    tool: str
    parameters: dict[str, Any]
    output: Any = None
    error: str | None = None
    success: bool = False
    duration: float = 0.0
    memory_mb: float | None = None
    cpu: float | None = None
    logs: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ExecutionRecorder:
    """
    Persists execution traces for debugging and replay.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or Path(settings.WORKSPACE_ROOT) / "execution_log.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, ExecutionRecord] = {}

    def record(
        self,
        *,
        tool: str,
        parameters: dict[str, Any],
        output: Any = None,
        error: str | None = None,
        success: bool = False,
        duration: float = 0.0,
        memory_mb: float | None = None,
        cpu: float | None = None,
        logs: list[str] | None = None,
    ) -> ExecutionRecord:
        record = ExecutionRecord(
            record_id=str(uuid4()),
            tool=tool,
            parameters=parameters,
            output=output,
            error=error,
            success=success,
            duration=duration,
            memory_mb=memory_mb,
            cpu=cpu,
            logs=logs or [],
        )
        self._records[record.record_id] = record
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), default=str) + "\n")
        return record

    def get(self, record_id: str) -> ExecutionRecord:
        if record_id not in self._records:
            raise KeyError(f"Record '{record_id}' not found.")
        return self._records[record_id]

    def list(self, limit: int = 50) -> list[ExecutionRecord]:
        return list(self._records.values())[-limit:]

    def replay(self, record_id: str) -> dict[str, Any]:
        record = self.get(record_id)
        return {
            "tool": record.tool,
            "parameters": record.parameters,
            "note": "Replay returns original inputs for re-execution by the kernel.",
        }


execution_recorder = ExecutionRecorder()
