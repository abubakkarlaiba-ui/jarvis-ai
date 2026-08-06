"""
Long-term memory for JARVIS.
==============================
Persistent storage for facts, preferences, and knowledge with
importance scoring, decay, and search capabilities.

This module provides the unified LongTermMemory interface used
by the MemorySystem orchestrator.

Usage:
    ltm = LongTermMemory(settings)
    await ltm.initialize()
    entry = await ltm.add("User prefers Python", category="preference")
    facts = await ltm.search_facts("programming language")
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.config.settings import MemorySettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry in long-term storage."""
    id: str
    content: str
    category: str
    confidence: float = 1.0
    created_at: datetime = field(default_factory=utc_now)
    last_accessed: datetime | None = None
    access_count: int = 0
    source_session: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "source_session": self.source_session,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            category=data.get("category", "general"),
            confidence=data.get("confidence", 1.0),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            access_count=data.get("access_count", 0),
            source_session=data.get("source_session", ""),
            metadata=data.get("metadata", {}),
        )


class LongTermMemory:
    """Persistent memory for facts and knowledge.

    Provides JSON-backed storage with importance scoring,
    access tracking, and keyword search.

    Example:
        ltm = LongTermMemory(settings)
        await ltm.initialize()
        entry = await ltm.add("User prefers dark mode", category="preference")
    """

    def __init__(self, settings: MemorySettings):
        self._settings = settings
        self._data_dir = Path(settings.data_dir)
        self._facts_file = self._data_dir / "long_term_facts.json"
        self._entries: dict[str, MemoryEntry] = {}

    async def initialize(self) -> None:
        """Initialize the long-term memory store."""
        ensure_directory(self._data_dir)
        self._load()
        logger.info("LongTermMemory initialized with %d entries", len(self._entries))

    def _load(self) -> None:
        """Load persisted entries from disk."""
        if self._facts_file.exists():
            try:
                data = json.loads(self._facts_file.read_text(encoding="utf-8"))
                for item in data:
                    entry = MemoryEntry.from_dict(item)
                    self._entries[entry.id] = entry
            except Exception as exc:
                logger.error("Failed to load long-term memory: %s", exc)

    def _save(self) -> None:
        """Persist entries to disk."""
        data = [entry.to_dict() for entry in self._entries.values()]
        self._facts_file.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    async def add(
        self,
        content: str,
        category: str = "general",
        importance: float = 1.0,
        metadata: dict[str, Any] | None = None,
        source_session: str = "",
    ) -> MemoryEntry:
        """Add a new memory entry.

        Args:
            content: Text content to remember.
            category: Category label.
            importance: Importance score (0.0-5.0).
            metadata: Additional metadata.
            source_session: Source session ID.

        Returns:
            The created MemoryEntry.
        """
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            confidence=importance,
            created_at=utc_now(),
            last_accessed=utc_now(),
            source_session=source_session,
            metadata=metadata or {},
        )
        self._entries[entry.id] = entry
        self._save()
        logger.debug("Stored fact: '%s' (cat=%s, imp=%.2f)", content[:60], category, importance)
        return entry

    async def get(self, entry_id: str) -> MemoryEntry | None:
        """Get a memory entry by ID."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.last_accessed = utc_now()
            entry.access_count += 1
            self._save()
        return entry

    async def get_all(self) -> list[MemoryEntry]:
        """Get all memory entries."""
        return list(self._entries.values())

    async def search_facts(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search facts by keyword matching.

        Args:
            query: Search terms.
            limit: Maximum results.

        Returns:
            Matching facts sorted by confidence and recency.
        """
        query_lower = query.lower()
        words = set(query_lower.split())

        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries.values():
            content_lower = entry.content.lower()
            overlap = sum(1 for w in words if w in content_lower)
            if overlap == 0:
                continue
            score = (overlap / len(words)) * entry.confidence
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for _, entry in scored[:limit]:
            entry.last_accessed = utc_now()
            entry.access_count += 1
            results.append(entry)

        if results:
            self._save()

        return results

    async def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._save()
            return True
        return False

    async def get_stats(self) -> dict:
        """Get statistics about the long-term memory."""
        categories: dict[str, int] = {}
        for entry in self._entries.values():
            categories[entry.category] = categories.get(entry.category, 0) + 1

        return {
            "total_entries": len(self._entries),
            "categories": categories,
            "avg_confidence": sum(e.confidence for e in self._entries.values()) / max(len(self._entries), 1),
        }
