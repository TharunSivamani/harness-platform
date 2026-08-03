from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class TaskState(str, Enum):
    NEW = "NEW"
    PLANNING = "PLANNING"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.NEW: {TaskState.PLANNING, TaskState.FAILED},
    TaskState.PLANNING: {TaskState.WAITING, TaskState.RUNNING, TaskState.FAILED},
    TaskState.WAITING: {TaskState.RUNNING, TaskState.PAUSED, TaskState.FAILED},
    TaskState.RUNNING: {
        TaskState.PAUSED,
        TaskState.RETRYING,
        TaskState.COMPLETED,
        TaskState.FAILED,
    },
    TaskState.PAUSED: {TaskState.RUNNING, TaskState.FAILED},
    TaskState.RETRYING: {TaskState.RUNNING, TaskState.FAILED},
    TaskState.COMPLETED: set(),
    TaskState.FAILED: {TaskState.RETRYING},
}


@dataclass
class TaskRecord:
    task_id: str
    state: TaskState = TaskState.NEW
    input: str = ""
    output: Any = None
    error: str | None = None
    retries: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class StateMachine:
    """
    Task lifecycle state machine with transition validation.
    """

    def __init__(self):
        self._tasks: dict[str, TaskRecord] = {}

    def create(self, input_text: str = "") -> TaskRecord:
        task = TaskRecord(task_id=str(uuid4()), input=input_text)
        task.history.append({"state": task.state.value, "at": task.created_at})
        self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> TaskRecord:
        if task_id not in self._tasks:
            raise KeyError(f"Task '{task_id}' not found.")
        return self._tasks[task_id]

    def transition(self, task_id: str, new_state: TaskState, **extra: Any) -> TaskRecord:
        task = self.get(task_id)
        allowed = ALLOWED_TRANSITIONS[task.state]
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition {task.state.value} -> {new_state.value}"
            )

        task.state = new_state
        task.updated_at = datetime.now(timezone.utc).isoformat()
        if "error" in extra:
            task.error = extra["error"]
        if "output" in extra:
            task.output = extra["output"]
        if new_state == TaskState.RETRYING:
            task.retries += 1

        entry = {"state": new_state.value, "at": task.updated_at}
        entry.update(extra)
        task.history.append(entry)
        return task

    def list_tasks(self) -> list[TaskRecord]:
        return list(self._tasks.values())


state_machine = StateMachine()
