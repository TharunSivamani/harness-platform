from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass
class ResourceLease:
    cpu: float
    memory_mb: int
    gpu: float = 0.0
    holder: str = ""


class ResourceScheduler:
    """
    Simple fair resource scheduler for CPU/memory/GPU budgets.
    """

    def __init__(self, cpu: float = 4.0, memory_mb: int = 4096, gpu: float = 0.0):
        self.total_cpu = cpu
        self.total_memory_mb = memory_mb
        self.total_gpu = gpu
        self._used_cpu = 0.0
        self._used_memory = 0
        self._used_gpu = 0.0
        self._lock = asyncio.Lock()
        self._leases: dict[str, ResourceLease] = {}
        self._waiters = 0

    @property
    def usage(self) -> dict[str, Any]:
        return {
            "cpu": {"used": self._used_cpu, "total": self.total_cpu},
            "memory_mb": {"used": self._used_memory, "total": self.total_memory_mb},
            "gpu": {"used": self._used_gpu, "total": self.total_gpu},
            "active_leases": len(self._leases),
            "waiters": self._waiters,
        }

    async def acquire(
        self,
        lease_id: str,
        *,
        cpu: float = 0.5,
        memory_mb: int = 256,
        gpu: float = 0.0,
        holder: str = "",
    ) -> ResourceLease:
        self._waiters += 1
        try:
            while True:
                async with self._lock:
                    if (
                        self._used_cpu + cpu <= self.total_cpu
                        and self._used_memory + memory_mb <= self.total_memory_mb
                        and self._used_gpu + gpu <= self.total_gpu
                    ):
                        self._used_cpu += cpu
                        self._used_memory += memory_mb
                        self._used_gpu += gpu
                        lease = ResourceLease(
                            cpu=cpu,
                            memory_mb=memory_mb,
                            gpu=gpu,
                            holder=holder,
                        )
                        self._leases[lease_id] = lease
                        return lease
                await asyncio.sleep(0.05)
        finally:
            self._waiters -= 1

    async def release(self, lease_id: str) -> None:
        async with self._lock:
            lease = self._leases.pop(lease_id, None)
            if not lease:
                return
            self._used_cpu = max(0.0, self._used_cpu - lease.cpu)
            self._used_memory = max(0, self._used_memory - lease.memory_mb)
            self._used_gpu = max(0.0, self._used_gpu - lease.gpu)


resource_scheduler = ResourceScheduler()
