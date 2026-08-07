# `app/observability/`

In-process metrics for latency and counters. Designed to grow into OpenTelemetry/Prometheus exporters.

## Files

| File | Purpose |
|------|---------|
| `metrics.py` | `MetricsRegistry` — bounded counters + timing aggregates |

## Features

- **Bounded timing samples**: Max 10,000 samples per metric (configurable)
- **Running statistics**: Tracks all-time min/max/count even after sample eviction
- **Thread-safe**: All operations are lock-protected

## Examples

```python
from app.observability.metrics import metrics

metrics.incr("chat.requests")
metrics.observe("agent.latency", 0.123)

snapshot = metrics.snapshot()
print(snapshot["timings"]["agent.latency"])
# {
#   "count": 1,              # Total observations
#   "samples_retained": 1,   # Samples in buffer
#   "avg": 0.123,           # Average of retained samples
#   "avg_all_time": 0.123,  # Average of all observations
#   "min": 0.123,           # All-time minimum
#   "max": 0.123,           # All-time maximum
# }
```

Fetch live metrics:

```bash
curl http://127.0.0.1:8000/metrics
```
