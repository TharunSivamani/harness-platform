from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4


@dataclass
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """
    In-process async event bus (Redis/Kafka-ready interface).
    """

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[Event] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        self._handlers["*"].append(handler)

    async def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> Event:
        event = Event(type=event_type, payload=payload or {})
        self._history.append(event)

        handlers = [*self._handlers.get(event_type, []), *self._handlers.get("*", [])]
        for handler in handlers:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        return event

    def history(self, event_type: str | None = None, limit: int = 100) -> list[Event]:
        events = self._history
        if event_type:
            events = [event for event in events if event.type == event_type]
        return events[-limit:]


event_bus = EventBus()
