"""
Execution recorder with log rotation support.

FIX: Added max_file_size_mb and max_backup_count to prevent unbounded disk
growth. Log files are automatically rotated when they exceed the size limit.
"""

from __future__ import annotations

import json
import os
import shutil
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.storage.paths import paths


# Default maximum log file size before rotation (10 MB)
DEFAULT_MAX_FILE_SIZE_MB = 10

# Default number of backup files to keep
DEFAULT_MAX_BACKUP_COUNT = 5

# Default maximum in-memory records to retain
DEFAULT_MAX_MEMORY_RECORDS = 1000


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
    Persists execution traces for debugging and replay with automatic log rotation.
    
    Features:
    - Automatic file rotation when log exceeds max_file_size_mb
    - Configurable number of backup files
    - Bounded in-memory record cache
    """

    def __init__(
        self,
        path: str | Path | None = None,
        max_file_size_mb: float = DEFAULT_MAX_FILE_SIZE_MB,
        max_backup_count: int = DEFAULT_MAX_BACKUP_COUNT,
        max_memory_records: int = DEFAULT_MAX_MEMORY_RECORDS,
    ):
        """
        Initialize the execution recorder.
        
        Args:
            path: Path to the JSONL log file
            max_file_size_mb: Maximum file size before rotation (MB)
            max_backup_count: Number of rotated backup files to keep
            max_memory_records: Maximum records to keep in memory
        """
        self.path = Path(path or paths.root / "execution_log.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        self._max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)
        self._max_backup_count = max_backup_count
        self._max_memory_records = max_memory_records
        
        # Use deque for bounded in-memory storage
        self._records: deque[ExecutionRecord] = deque(maxlen=max_memory_records)
        self._record_index: dict[str, ExecutionRecord] = {}
        self._total_recorded: int = 0

    def _should_rotate(self) -> bool:
        """Check if log file exceeds size limit."""
        if not self.path.exists():
            return False
        try:
            return self.path.stat().st_size >= self._max_file_size_bytes
        except OSError:
            return False

    def _rotate_logs(self) -> None:
        """
        Rotate log files: current -> .1, .1 -> .2, etc.
        Deletes oldest backup if exceeding max_backup_count.
        """
        if not self.path.exists():
            return
        
        # Delete oldest backup if it exists
        oldest = self.path.with_suffix(f".jsonl.{self._max_backup_count}")
        if oldest.exists():
            try:
                oldest.unlink()
            except OSError:
                pass
        
        # Rotate existing backups: .4 -> .5, .3 -> .4, etc.
        for i in range(self._max_backup_count - 1, 0, -1):
            src = self.path.with_suffix(f".jsonl.{i}")
            dst = self.path.with_suffix(f".jsonl.{i + 1}")
            if src.exists():
                try:
                    shutil.move(str(src), str(dst))
                except OSError:
                    pass
        
        # Rotate current to .1
        backup_1 = self.path.with_suffix(".jsonl.1")
        try:
            shutil.move(str(self.path), str(backup_1))
        except OSError:
            # If rotation fails, truncate the file instead
            try:
                self.path.write_text("")
            except OSError:
                pass

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
        """
        Record an execution trace.
        
        The record is stored in memory (bounded) and appended to the log file.
        Log rotation occurs automatically when file size exceeds the limit.
        """
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
        
        # Check for rotation before writing
        if self._should_rotate():
            self._rotate_logs()
        
        # Add to in-memory storage
        # If deque is at capacity, remove evicted record from index
        if len(self._records) == self._max_memory_records:
            evicted = self._records[0]
            self._record_index.pop(evicted.record_id, None)
        
        self._records.append(record)
        self._record_index[record.record_id] = record
        self._total_recorded += 1
        
        # Append to log file
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(record), default=str) + "\n")
        except OSError:
            # Log write failure is non-fatal - record is still in memory
            pass
        
        return record

    def get(self, record_id: str) -> ExecutionRecord:
        """Get a record by ID from the in-memory cache."""
        if record_id not in self._record_index:
            raise KeyError(f"Record '{record_id}' not found in memory cache.")
        return self._record_index[record_id]

    def list(self, limit: int = 50) -> list[ExecutionRecord]:
        """List recent records from memory."""
        records = list(self._records)
        return records[-limit:]

    def replay(self, record_id: str) -> dict[str, Any]:
        """Get original inputs for re-execution."""
        record = self.get(record_id)
        return {
            "tool": record.tool,
            "parameters": record.parameters,
            "note": "Replay returns original inputs for re-execution by the kernel.",
        }

    def stats(self) -> dict[str, Any]:
        """Get recorder statistics."""
        file_size = 0
        if self.path.exists():
            try:
                file_size = self.path.stat().st_size
            except OSError:
                pass
        
        backup_count = sum(
            1 for i in range(1, self._max_backup_count + 1)
            if self.path.with_suffix(f".jsonl.{i}").exists()
        )
        
        return {
            "total_recorded": self._total_recorded,
            "memory_records": len(self._records),
            "max_memory_records": self._max_memory_records,
            "log_file_size_bytes": file_size,
            "max_file_size_bytes": self._max_file_size_bytes,
            "backup_count": backup_count,
            "max_backup_count": self._max_backup_count,
        }


execution_recorder = ExecutionRecorder()
