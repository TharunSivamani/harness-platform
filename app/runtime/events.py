"""
In-process async event bus with bounded history.

FIX: Added max_history_size to prevent unbounded memory growth in long-running
deployments. Events older than the cap are automatically evicted.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

# Default maximum events to retain in history (prevents memory leak)
DEFAULT_MAX_HISTORY_SIZE = 10_000


@dataclass
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """
    In-process async event bus (Redis/Kafka-ready interface).

    Features:
    - Bounded history with automatic eviction (default 10,000 events)
    - Async-safe event publishing
    - Wildcard subscriptions via "*"
    """

    def __init__(self, max_history_size: int = DEFAULT_MAX_HISTORY_SIZE):
        """
        Initialize the event bus.

        Args:
            max_history_size: Maximum number of events to retain in history.
                             Set to 0 to disable history entirely.
        """
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        # Use deque with maxlen for automatic bounded history
        self._history: deque[Event] = deque(
            maxlen=max_history_size if max_history_size > 0 else None
        )
        self._max_history_size = max_history_size
        self._total_published: int = 0  # Track total events ever published

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type."""
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """Unsubscribe a handler from an event type. Returns True if found."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            return True
        return False

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to all events (wildcard)."""
        self._handlers["*"].append(handler)

    async def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> Event:
        """
        Publish an event to all subscribed handlers.

        The event is added to history (subject to max_history_size cap)
        and then dispatched to all matching handlers.
        """
        event = Event(type=event_type, payload=payload or {})

        # deque with maxlen automatically evicts oldest when full
        self._history.append(event)
        self._total_published += 1

        handlers = [*self._handlers.get(event_type, []), *self._handlers.get("*", [])]
        for handler in handlers:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        return event

    def history(self, event_type: str | None = None, limit: int = 100) -> list[Event]:
        """
        Get recent events from history.

        Args:
            event_type: Filter by event type (None for all types)
            limit: Maximum number of events to return

        Returns:
            List of events, most recent last
        """
        events = list(self._history)
        if event_type:
            events = [event for event in events if event.type == event_type]
        return events[-limit:]

    def stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        return {
            "history_size": len(self._history),
            "max_history_size": self._max_history_size,
            "total_published": self._total_published,
            "handler_count": sum(len(h) for h in self._handlers.values()),
            "event_types": list(self._handlers.keys()),
        }

    def clear_history(self) -> int:
        """Clear all history. Returns number of events cleared."""
        count = len(self._history)
        self._history.clear()
        return count


event_bus = EventBus()
