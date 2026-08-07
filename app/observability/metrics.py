"""
Lightweight in-process metrics for latency, counters, and token/cost tracking.

FIX: Added max_timing_samples to prevent unbounded memory growth in long-running
deployments. Timing samples are kept in a bounded circular buffer per metric.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import time
from typing import Any


# Default maximum timing samples to retain per metric
DEFAULT_MAX_TIMING_SAMPLES = 10_000


class MetricsRegistry:
    """
    Lightweight in-process metrics for latency, counters, and token/cost tracking.
    
    Features:
    - Bounded timing samples with automatic eviction (default 10,000 per metric)
    - Thread-safe operations
    - Running statistics without storing all samples
    """

    def __init__(self, max_timing_samples: int = DEFAULT_MAX_TIMING_SAMPLES):
        """
        Initialize the metrics registry.
        
        Args:
            max_timing_samples: Maximum timing samples to retain per metric.
                               Older samples are evicted when limit is reached.
        """
        self._lock = Lock()
        self.counters: dict[str, float] = defaultdict(float)
        # Use deque with maxlen for automatic bounded storage
        self._timings: dict[str, deque[float]] = {}
        self._max_timing_samples = max_timing_samples
        # Track running stats for accurate min/max even after eviction
        self._timing_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "sum": 0.0, "min": float("inf"), "max": float("-inf")}
        )
        self.started_at = time()

    def _get_timing_deque(self, name: str) -> deque[float]:
        """Get or create a bounded deque for timing samples."""
        if name not in self._timings:
            self._timings[name] = deque(maxlen=self._max_timing_samples)
        return self._timings[name]

    def incr(self, name: str, value: float = 1.0) -> None:
        """Increment a counter by value (default 1)."""
        with self._lock:
            self.counters[name] += value

    def observe(self, name: str, value: float) -> None:
        """Record a timing observation."""
        with self._lock:
            # Add to bounded sample buffer
            samples = self._get_timing_deque(name)
            samples.append(value)
            
            # Update running statistics
            stats = self._timing_stats[name]
            stats["count"] += 1
            stats["sum"] += value
            stats["min"] = min(stats["min"], value)
            stats["max"] = max(stats["max"], value)

    def snapshot(self) -> dict[str, Any]:
        """
        Get a snapshot of all metrics.
        
        Returns dict with:
        - uptime_seconds: Time since registry creation
        - counters: All counter values
        - timings: Statistics for each timing metric
        """
        with self._lock:
            timing_stats = {}
            for key, samples in self._timings.items():
                if not samples:
                    continue
                running = self._timing_stats[key]
                # Calculate stats from current sample buffer
                sample_list = list(samples)
                timing_stats[key] = {
                    "count": running["count"],  # Total ever observed
                    "samples_retained": len(sample_list),
                    "avg": sum(sample_list) / len(sample_list),  # Avg of retained samples
                    "avg_all_time": running["sum"] / running["count"] if running["count"] > 0 else 0,
                    "max": running["max"],  # All-time max
                    "min": running["min"] if running["min"] != float("inf") else 0,  # All-time min
                    "max_retained": max(sample_list),  # Max of retained samples
                    "min_retained": min(sample_list),  # Min of retained samples
                }
            return {
                "uptime_seconds": time() - self.started_at,
                "counters": dict(self.counters),
                "timings": timing_stats,
            }

    def get_counter(self, name: str) -> float:
        """Get current value of a counter."""
        with self._lock:
            return self.counters.get(name, 0.0)

    def get_timing_samples(self, name: str, limit: int | None = None) -> list[float]:
        """Get recent timing samples for a metric."""
        with self._lock:
            samples = list(self._timings.get(name, []))
            if limit:
                return samples[-limit:]
            return samples

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self.counters.clear()
            self._timings.clear()
            self._timing_stats.clear()
            self.started_at = time()


metrics = MetricsRegistry()
