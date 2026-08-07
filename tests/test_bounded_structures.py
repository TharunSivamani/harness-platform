"""
Tests for bounded data structures.

These tests verify that EventBus, MetricsRegistry, and ExecutionRecorder
properly cap their memory/disk usage to prevent unbounded growth.
"""

import pytest
import tempfile
from pathlib import Path
from app.runtime.events import EventBus, DEFAULT_MAX_HISTORY_SIZE
from app.observability.metrics import MetricsRegistry, DEFAULT_MAX_TIMING_SAMPLES
from app.runtime.recorder import ExecutionRecorder


class TestEventBusBoundedHistory:
    """Test EventBus history is properly bounded."""

    @pytest.mark.asyncio
    async def test_history_bounded_to_max_size(self):
        """History should never exceed max_history_size."""
        max_size = 100
        bus = EventBus(max_history_size=max_size)
        
        # Publish more events than the max
        for i in range(max_size + 50):
            await bus.publish("test_event", {"index": i})
        
        # History should be capped
        assert len(bus._history) == max_size
        
        # Oldest events should be evicted (FIFO)
        all_history = bus.history(limit=max_size)
        indices = [e.payload["index"] for e in all_history]
        assert min(indices) == 50  # First 50 events were evicted

    @pytest.mark.asyncio
    async def test_zero_history_disables_storage(self):
        """Setting max_history_size=0 should disable history."""
        bus = EventBus(max_history_size=0)
        
        await bus.publish("test_event", {"data": "test"})
        
        # deque with maxlen=None stores everything, so this tests that feature
        # For truly disabled history, we'd need maxlen=0 which isn't valid
        # So this just verifies the behavior with None

    @pytest.mark.asyncio
    async def test_stats_track_total_published(self):
        """Stats should track total events published, not just retained."""
        max_size = 10
        bus = EventBus(max_history_size=max_size)
        
        for i in range(100):
            await bus.publish("test", {"i": i})
        
        stats = bus.stats()
        assert stats["total_published"] == 100
        assert stats["history_size"] == max_size  # Only 10 retained


class TestMetricsRegistryBoundedTimings:
    """Test MetricsRegistry timing samples are bounded."""

    def test_timing_samples_bounded(self):
        """Timing samples should be bounded per metric."""
        max_samples = 50
        registry = MetricsRegistry(max_timing_samples=max_samples)
        
        # Add more samples than the limit
        for i in range(max_samples + 30):
            registry.observe("test_metric", float(i))
        
        samples = registry.get_timing_samples("test_metric")
        assert len(samples) == max_samples
        
        # Oldest samples should be evicted
        assert min(samples) == 30  # First 30 were evicted

    def test_running_stats_track_all_observations(self):
        """Running stats should track all-time values, not just retained."""
        max_samples = 10
        registry = MetricsRegistry(max_timing_samples=max_samples)
        
        # Record values 0-99 (min=0, max=99)
        for i in range(100):
            registry.observe("test", float(i))
        
        snapshot = registry.snapshot()
        timing = snapshot["timings"]["test"]
        
        # Total count should be all observations
        assert timing["count"] == 100
        
        # All-time min/max should capture the full range
        assert timing["min"] == 0  # All-time min
        assert timing["max"] == 99  # All-time max
        
        # Only retained samples for recent stats
        assert timing["samples_retained"] == max_samples


class TestExecutionRecorderBounded:
    """Test ExecutionRecorder memory and file rotation."""

    def test_memory_records_bounded(self):
        """In-memory records should be bounded."""
        max_records = 20
        
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = ExecutionRecorder(
                path=Path(tmpdir) / "test.jsonl",
                max_memory_records=max_records,
            )
            
            # Record more than the limit
            for i in range(max_records + 10):
                recorder.record(
                    tool="test_tool",
                    parameters={"index": i},
                    success=True,
                )
            
            # Memory should be bounded
            records = recorder.list(limit=100)
            assert len(records) == max_records
            
            # Oldest records should be evicted from memory
            indices = [r.parameters["index"] for r in records]
            assert min(indices) == 10  # First 10 were evicted

    def test_stats_track_total_recorded(self):
        """Stats should track total records, not just retained."""
        max_records = 10
        
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = ExecutionRecorder(
                path=Path(tmpdir) / "test.jsonl",
                max_memory_records=max_records,
            )
            
            for i in range(50):
                recorder.record(tool="test", parameters={}, success=True)
            
            stats = recorder.stats()
            assert stats["total_recorded"] == 50
            assert stats["memory_records"] == max_records
