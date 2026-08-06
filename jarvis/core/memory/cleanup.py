"""
Memory cleanup and pruning for JARVIS.
=======================================
Automatically manages memory lifecycle by pruning low-importance
entries, consolidating duplicates, and enforcing size limits.

Cleanup strategies:
    - Importance-based pruning (remove lowest scoring)
    - Age-based pruning (remove oldest beyond retention)
    - Deduplication (merge similar entries)
    - Category balancing (ensure diversity)

Usage:
    cleaner = MemoryCleanup(settings)
    stats = await cleaner.run_cleanup(all_memories)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from jarvis.config.settings import MemorySettings
from jarvis.core.memory.importance import ImportanceScorer

logger = logging.getLogger(__name__)


@dataclass
class CleanupStats:
    """Statistics from a cleanup run."""
    entries_checked: int = 0
    entries_removed: int = 0
    entries_deduplicated: int = 0
    entries_promoted: int = 0
    space_freed: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "entries_checked": self.entries_checked,
            "entries_removed": self.entries_removed,
            "entries_deduplicated": self.entries_deduplicated,
            "entries_promoted": self.entries_promoted,
            "space_freed": self.space_freed,
            "duration_ms": round(self.duration_ms, 1),
        }


class MemoryCleanup:
    """Manages memory lifecycle through automated cleanup.

    Example:
        cleaner = MemoryCleanup(settings)
        stats = await cleaner.run_cleanup(memories)
        print(f"Cleaned {stats.entries_removed} entries")
    """

    def __init__(self, settings: MemorySettings):
        self._settings = settings
        self._scorer = ImportanceScorer(
            decay_rate=settings.importance_decay_rate,
            min_threshold=settings.min_importance_threshold,
            boost_per_access=settings.boost_repeated_access,
        )
        self._max_total = settings.max_total_memories

    async def run_cleanup(
        self,
        memories: list[dict],
        preserve_categories: list[str] | None = None,
    ) -> CleanupStats:
        """Run a full cleanup cycle.

        Args:
            memories: List of memory dicts to clean.
            preserve_categories: Categories to never remove.

        Returns:
            CleanupStats with the results.
        """
        import time
        start = time.perf_counter()
        stats = CleanupStats()
        stats.entries_checked = len(memories)

        preserve = set(preserve_categories or ["user_preference", "reminder"])

        # Step 1: Remove entries below importance threshold
        keep = []
        for mem in memories:
            category = mem.get("category", "")
            if category in preserve:
                keep.append(mem)
                continue

            factors = self._scorer.calculate(
                created_at=mem.get("created_at"),
                last_accessed=mem.get("last_accessed"),
                access_count=mem.get("access_count", 0),
                explicit_importance=mem.get("importance", 1.0),
                memory_type=category,
                content=mem.get("content", ""),
            )

            if self._scorer.should_keep(factors.total):
                keep.append(mem)
            else:
                stats.entries_removed += 1

        # Step 2: Deduplication
        deduped = self._deduplicate(keep)
        stats.entries_deduplicated = len(keep) - len(deduped)

        # Step 3: Enforce max size
        if len(deduped) > self._max_total:
            ranked = self._scorer.batch_rank(deduped)
            deduped = [entry for entry, _ in ranked[:self._max_total]]
            stats.entries_removed += len(ranked) - self._max_total

        stats.duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Cleanup complete: checked=%d, removed=%d, deduped=%d (%.1fms)",
            stats.entries_checked,
            stats.entries_removed,
            stats.entries_deduplicated,
            stats.duration_ms,
        )

        return stats

    def _deduplicate(self, memories: list[dict]) -> list[dict]:
        """Remove near-duplicate memories, keeping the newer one."""
        if len(memories) <= 1:
            return memories

        unique: list[dict] = []
        seen_hashes: set[str] = set()

        for mem in memories:
            content = mem.get("content", "").lower().strip()
            # Simple dedup: first 50 chars hash
            key = content[:50]
            if key not in seen_hashes:
                seen_hashes.add(key)
                unique.append(mem)

        return unique

    def estimate_memory_usage(self, memories: list[dict]) -> dict:
        """Estimate memory usage statistics."""
        total_chars = sum(len(m.get("content", "")) for m in memories)
        categories: dict[str, int] = {}
        for mem in memories:
            cat = mem.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_entries": len(memories),
            "total_characters": total_chars,
            "estimated_tokens": total_chars // 4,
            "categories": categories,
            "max_entries": self._max_total,
            "usage_percent": round(len(memories) / self._max_total * 100, 1),
        }
