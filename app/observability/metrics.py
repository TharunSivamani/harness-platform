from __future__ import annotations

from collections import defaultdict
from threading import Lock
from time import time


class MetricsRegistry:
    """
    Lightweight in-process metrics for latency, counters, and token/cost tracking.
    """

    def __init__(self):
        self._lock = Lock()
        self.counters: dict[str, float] = defaultdict(float)
        self.timings: dict[str, list[float]] = defaultdict(list)
        self.started_at = time()

    def incr(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            self.counters[name] += value

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self.timings[name].append(value)

    def snapshot(self) -> dict:
        with self._lock:
            timing_stats = {}
            for key, values in self.timings.items():
                if not values:
                    continue
                timing_stats[key] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "max": max(values),
                    "min": min(values),
                }
            return {
                "uptime_seconds": time() - self.started_at,
                "counters": dict(self.counters),
                "timings": timing_stats,
            }


metrics = MetricsRegistry()
