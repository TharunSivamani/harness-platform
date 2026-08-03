# `app/observability/`

In-process metrics for latency and counters. Designed to grow into OpenTelemetry/Prometheus exporters.

## Files

| File | Purpose |
|------|---------|
| `metrics.py` | `MetricsRegistry` counters + timing aggregates |

## Examples

```python
from app.observability.metrics import metrics

metrics.incr("chat.requests")
metrics.observe("agent.latency", 0.123)
print(metrics.snapshot())
```

Fetch live metrics:

```bash
curl http://127.0.0.1:8000/metrics
```
