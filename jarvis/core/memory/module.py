"""
Memory module — short-term, long-term, and vector-based memory.
================================================================
Provides a layered memory system for context retention and knowledge retrieval.

Layers:
    ShortTermMemory   — recent conversation turns (in-memory deque)
    LongTermMemory    — persisted facts and preferences (JSON/file-backed)
    VectorMemory      — semantic search over embeddings (vector store)

Usage:
    memory = MemoryModule(settings)
    await memory.store("user prefers dark mode")
    results = await memory.recall("what does the user prefer?")
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from jarvis.config.settings import MemorySettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory record."""
    id: str
    content: str
    category: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 1.0
    embedding: list[float] | None = None


class ShortTermMemory:
    """Fixed-capacity in-memory buffer for recent conversation turns.

    Entries are stored in a deque and automatically evicted when full.
    """

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self._buffer: deque[MemoryEntry] = deque(maxlen=max_items)

    def store(self, content: str, category: str = "conversation", **kwargs: Any) -> MemoryEntry:
        """Store a new entry in short-term memory.

        Args:
            content: Text content of the memory.
            category: Category label (conversation, observation, etc.).
            **kwargs: Additional metadata fields.

        Returns:
            The created MemoryEntry.
        """
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            timestamp=utc_now(),
            metadata=kwargs,
        )
        self._buffer.append(entry)
        logger.debug("ShortTermMemory: stored '%s' (id=%s)", content[:50], entry.id)
        return entry

    def recall(self, n: int = 10) -> list[MemoryEntry]:
        """Return the most recent n entries."""
        return list(self._buffer)[-n:]

    def search(self, query: str) -> list[MemoryEntry]:
        """Simple substring search across stored entries."""
        query_lower = query.lower()
        return [e for e in self._buffer if query_lower in e.content.lower()]

    def clear(self) -> None:
        """Clear all short-term memory."""
        self._buffer.clear()

    @property
    def size(self) -> int:
        return len(self._buffer)


class LongTermMemory:
    """File-backed persistent memory for facts, preferences, and knowledge.

    Entries are stored as JSON and loaded on initialization.
    """

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)
        ensure_directory(self.storage_path.parent)
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load persisted entries from disk."""
        data_file = self.storage_path
        if data_file.exists():
            try:
                data = json.loads(data_file.read_text(encoding="utf-8"))
                for item in data:
                    entry = MemoryEntry(
                        id=item["id"],
                        content=item["content"],
                        category=item["category"],
                        timestamp=datetime.fromisoformat(item["timestamp"]),
                        metadata=item.get("metadata", {}),
                        importance=item.get("importance", 1.0),
                    )
                    self._entries[entry.id] = entry
                logger.info("LongTermMemory: loaded %d entries", len(self._entries))
            except Exception as exc:
                logger.error("LongTermMemory: failed to load — %s", exc)

    def _save(self) -> None:
        """Persist all entries to disk."""
        data = []
        for entry in self._entries.values():
            data.append({
                "id": entry.id,
                "content": entry.content,
                "category": entry.category,
                "timestamp": entry.timestamp.isoformat(),
                "metadata": entry.metadata,
                "importance": entry.importance,
            })
        self.storage_path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def store(self, content: str, category: str = "fact", **kwargs: Any) -> MemoryEntry:
        """Store a new entry in long-term memory.

        Args:
            content: Text content to remember.
            category: Category label (fact, preference, event, etc.).
            **kwargs: Additional metadata.

        Returns:
            The created MemoryEntry.
        """
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            timestamp=utc_now(),
            metadata=kwargs,
        )
        self._entries[entry.id] = entry
        self._save()
        logger.info("LongTermMemory: stored '%s' (id=%s)", content[:50], entry.id)
        return entry

    def search(self, query: str) -> list[MemoryEntry]:
        """Search entries by substring match on content.

        Args:
            query: Search string.

        Returns:
            List of matching MemoryEntry objects.
        """
        query_lower = query.lower()
        return [
            e for e in self._entries.values()
            if query_lower in e.content.lower()
        ]

    def get_by_category(self, category: str) -> list[MemoryEntry]:
        """Return all entries in a given category."""
        return [e for e in self._entries.values() if e.category == category]

    def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID. Returns True if found and deleted."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._save()
            return True
        return False

    @property
    def size(self) -> int:
        return len(self._entries)


class VectorMemory:
    """Semantic memory using vector embeddings for similarity search.

    Stores entries with embeddings and provides cosine-similarity retrieval.
    Uses a simple in-memory index; swap for FAISS/Chroma in production.
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self._entries: list[MemoryEntry] = []

    def store(self, content: str, embedding: list[float], category: str = "semantic", **kwargs: Any) -> MemoryEntry:
        """Store an entry with a precomputed embedding.

        Args:
            content: Text content.
            embedding: Vector representation of the content.
            category: Category label.
            **kwargs: Additional metadata.

        Returns:
            The created MemoryEntry.
        """
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            timestamp=utc_now(),
            metadata=kwargs,
            embedding=embedding,
        )
        self._entries.append(entry)
        logger.debug("VectorMemory: stored entry (id=%s)", entry.id)
        return entry

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[MemoryEntry, float]]:
        """Find the top_k most similar entries by cosine similarity.

        Args:
            query_embedding: Vector to compare against.
            top_k: Number of results to return.

        Returns:
            List of (MemoryEntry, similarity_score) tuples sorted by relevance.
        """
        import math

        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = []
        for entry in self._entries:
            if entry.embedding:
                score = cosine_sim(query_embedding, entry.embedding)
                scored.append((entry, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()

    @property
    def size(self) -> int:
        return len(self._entries)


class MemoryModule:
    """Unified memory interface coordinating all memory layers.

    Routes operations to the appropriate memory subsystem based on
    the type of information being stored or recalled.

    Example:
        memory = MemoryModule(settings)
        await memory.store("User prefers compact responses")
        results = await memory.recall("response preferences")
    """

    def __init__(self, settings: MemorySettings):
        self.short_term = ShortTermMemory(max_items=settings.short_term_max_items)
        self.long_term = LongTermMemory(
            storage_path=Path(settings.vector_store_path).parent / "long_term.json"
        )
        self.vector = VectorMemory(dimension=settings.embedding_dimension)
        self._settings = settings
        logger.info("MemoryModule initialized")

    async def store(self, content: str, category: str = "general", layer: str = "short_term", **kwargs: Any) -> MemoryEntry:
        """Store information in the specified memory layer.

        Args:
            content: Text to remember.
            category: Category label.
            layer: Target layer — 'short_term', 'long_term', or 'vector'.
            **kwargs: Additional metadata.

        Returns:
            The created MemoryEntry.
        """
        if layer == "short_term":
            return self.short_term.store(content, category, **kwargs)
        elif layer == "long_term":
            return self.long_term.store(content, category, **kwargs)
        elif layer == "vector":
            raise ValueError("Vector store requires an embedding; use store_with_embedding()")
        raise ValueError(f"Unknown memory layer: {layer}")

    async def store_with_embedding(self, content: str, embedding: list[float], category: str = "semantic", **kwargs: Any) -> MemoryEntry:
        """Store information in the vector memory with an embedding."""
        return self.vector.store(content, embedding, category, **kwargs)

    async def recall(self, query: str, layer: str = "short_term", **kwargs: Any) -> list[MemoryEntry]:
        """Recall memories matching a query from the specified layer.

        Args:
            query: Search query.
            layer: Source layer — 'short_term', 'long_term', or 'all'.
            **kwargs: Additional search parameters.

        Returns:
            List of matching MemoryEntry objects.
        """
        if layer == "short_term":
            return self.short_term.search(query)
        elif layer == "long_term":
            return self.long_term.search(query)
        elif layer == "all":
            results = self.short_term.search(query)
            results.extend(self.long_term.search(query))
            return results
        raise ValueError(f"Unknown memory layer: {layer}")

    async def get_stats(self) -> dict[str, int]:
        """Return memory usage statistics."""
        return {
            "short_term_count": self.short_term.size,
            "long_term_count": self.long_term.size,
            "vector_count": self.vector.size,
        }
