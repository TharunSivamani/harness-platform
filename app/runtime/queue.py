from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.core.config import settings


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Job:
    job_id: str
    name: str
    payload: dict[str, Any]
    priority: int = 100
    status: JobStatus = JobStatus.QUEUED
    retries: int = 0
    max_retries: int = 2
    result: Any = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class TaskQueue:
    """
    In-memory async task queue with worker pool.

    Interface is Redis/Celery-compatible for future backends.
    """

    def __init__(self, workers: int | None = None):
        self.workers = workers or settings.TASK_WORKERS
        self._queue: asyncio.PriorityQueue[tuple[int, str, Job]] = asyncio.PriorityQueue()
        self._jobs: dict[str, Job] = {}
        self._handlers: dict[str, Callable[[Job], Awaitable[Any]]] = {}
        self._started = False
        self._worker_tasks: list[asyncio.Task] = []

    def register(self, name: str, handler: Callable[[Job], Awaitable[Any]]) -> None:
        self._handlers[name] = handler

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        for index in range(self.workers):
            self._worker_tasks.append(asyncio.create_task(self._worker(index)))

    async def stop(self) -> None:
        for task in self._worker_tasks:
            task.cancel()
        self._worker_tasks.clear()
        self._started = False

    async def enqueue(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
        priority: int = 100,
        max_retries: int = 2,
    ) -> Job:
        await self.start()
        job = Job(
            job_id=str(uuid4()),
            name=name,
            payload=payload or {},
            priority=priority,
            max_retries=max_retries,
        )
        self._jobs[job.job_id] = job
        await self._queue.put((priority, job.created_at, job))
        return job

    def get(self, job_id: str) -> Job:
        if job_id not in self._jobs:
            raise KeyError(f"Job '{job_id}' not found.")
        return self._jobs[job_id]

    async def _worker(self, worker_id: int) -> None:
        while True:
            _, _, job = await self._queue.get()
            handler = self._handlers.get(job.name)
            if handler is None:
                job.status = JobStatus.FAILED
                job.error = f"No handler registered for '{job.name}'"
                continue

            job.status = JobStatus.RUNNING
            try:
                job.result = await handler(job)
                job.status = JobStatus.SUCCEEDED
            except Exception as exc:  # noqa: BLE001
                if job.retries < job.max_retries:
                    job.retries += 1
                    job.status = JobStatus.RETRYING
                    await self._queue.put((job.priority, job.created_at, job))
                else:
                    job.status = JobStatus.FAILED
                    job.error = str(exc)


task_queue = TaskQueue()
