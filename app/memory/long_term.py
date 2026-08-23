from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class MemoryItem:
    memory_id: str
    content: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class LongTermMemory:
    """
    Simple keyword long-term memory store.

    Future: embeddings + vector retrieval.
    """

    def __init__(self):
        self._items: dict[str, MemoryItem] = {}

    def store(
        self,
        content: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        item = MemoryItem(
            memory_id=str(uuid4()),
            content=content,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._items[item.memory_id] = item
        return item

    def retrieve(self, query: str, limit: int = 5) -> list[MemoryItem]:
        tokens = {token.lower() for token in query.split() if token.strip()}
        if not tokens:
            return []

        scored: list[tuple[int, MemoryItem]] = []
        for item in self._items.values():
            haystack = " ".join([item.content, *item.tags]).lower()
            score = sum(1 for token in tokens if token in haystack)
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def list_all(self) -> list[MemoryItem]:
        return list(self._items.values())


long_term_memory = LongTermMemory()
