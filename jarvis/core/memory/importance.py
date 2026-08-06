"""
Memory importance scoring for JARVIS.
======================================
Calculates and maintains importance scores for all memories to determine
what to keep, what to prune, and what to surface first.

Scoring factors:
    - Recency: newer memories score higher
    - Access frequency: frequently accessed memories score higher
    - Explicit importance: user-assigned importance
    - Relevance: semantic similarity to current context
    - Type weight: some memory types are inherently more important

Usage:
    scorer = ImportanceScorer(settings)
    score = scorer.score(memory_entry, context="current topic")
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from jarvis.utils.helpers import utc_now

logger = logging.getLogger(__name__)


@dataclass
class ImportanceFactors:
    """Breakdown of importance scoring factors."""
    recency: float = 0.0
    frequency: float = 0.0
    explicit: float = 0.0
    relevance: float = 0.0
    type_weight: float = 0.0
    total: float = 0.0


# Weight assigned to each factor
FACTOR_WEIGHTS = {
    "recency": 0.25,
    "frequency": 0.20,
    "explicit": 0.30,
    "relevance": 0.15,
    "type_weight": 0.10,
}

# Type-based importance weights
TYPE_WEIGHTS = {
    "user_preference": 0.9,
    "fact": 0.7,
    "decision": 0.8,
    "project": 0.7,
    "reminder": 0.85,
    "note": 0.6,
    "conversation": 0.4,
    "observation": 0.3,
    "summary": 0.5,
}


class ImportanceScorer:
    """Calculates importance scores for memory entries.

    The scorer combines multiple signals to produce a single importance
    score between 0.0 and 1.0. This score determines:
        - Which memories to keep during cleanup
        - Which memories to surface first during retrieval
        - Which memories to include in context injection

    Example:
        scorer = ImportanceScorer(settings)
        score = scorer.calculate(entry)
        scorer.update_access(entry)
    """

    def __init__(
        self,
        decay_rate: float = 0.01,
        boost_per_access: float = 0.05,
        min_threshold: float = 0.1,
    ):
        self.decay_rate = decay_rate
        self.boost_per_access = boost_per_access
        self.min_threshold = min_threshold

    def calculate(
        self,
        created_at: datetime | str | None = None,
        last_accessed: datetime | str | None = None,
        access_count: int = 0,
        explicit_importance: float = 1.0,
        memory_type: str = "fact",
        content: str = "",
        context: str = "",
    ) -> ImportanceFactors:
        """Calculate the importance score for a memory.

        Args:
            created_at: When the memory was created.
            last_accessed: When last accessed.
            access_count: Number of times accessed.
            explicit_importance: User-assigned importance (0-1).
            memory_type: Type of memory (fact, preference, etc.).
            content: Memory content text.
            context: Current context for relevance scoring.

        Returns:
            ImportanceFactors with breakdown and total score.
        """
        now = utc_now()

        # Parse datetime strings
        if isinstance(created_at, str) and created_at:
            created_at = datetime.fromisoformat(created_at)
        if isinstance(last_accessed, str) and last_accessed:
            last_accessed = datetime.fromisoformat(last_accessed)

        # 1. Recency score (decays over time)
        if created_at:
            age_days = (now - created_at).total_seconds() / 86400
            recency = math.exp(-self.decay_rate * age_days)
        else:
            recency = 0.5

        # 2. Frequency score (boosts with access)
        freq_score = min(1.0, 0.1 + access_count * self.boost_per_access)

        # 3. Explicit importance
        explicit = max(0.0, min(1.0, explicit_importance))

        # 4. Relevance to current context
        relevance = 0.0
        if context and content:
            context_words = set(context.lower().split())
            content_words = set(content.lower().split())
            if context_words:
                overlap = len(context_words & content_words)
                relevance = min(1.0, overlap / len(context_words))

        # 5. Type weight
        type_weight = TYPE_WEIGHTS.get(memory_type, 0.5)

        # Weighted total
        total = (
            recency * FACTOR_WEIGHTS["recency"]
            + freq_score * FACTOR_WEIGHTS["frequency"]
            + explicit * FACTOR_WEIGHTS["explicit"]
            + relevance * FACTOR_WEIGHTS["relevance"]
            + type_weight * FACTOR_WEIGHTS["type_weight"]
        )

        return ImportanceFactors(
            recency=round(recency, 4),
            frequency=round(freq_score, 4),
            explicit=round(explicit, 4),
            relevance=round(relevance, 4),
            type_weight=round(type_weight, 4),
            total=round(total, 4),
        )

    def should_keep(self, score: float) -> bool:
        """Determine if a memory should be kept based on its score."""
        return score >= self.min_threshold

    def should_surface(self, score: float, top_k: int = 5, current_rank: int = 0) -> bool:
        """Determine if a memory should be surfaced in context."""
        return current_rank < top_k and score > 0.3

    def batch_rank(self, entries: list[dict]) -> list[tuple[dict, float]]:
        """Rank a batch of memory entries by importance.

        Args:
            entries: List of dicts with scoring-relevant fields.

        Returns:
            List of (entry, score) tuples sorted by importance.
        """
        scored = []
        for entry in entries:
            factors = self.calculate(
                created_at=entry.get("created_at"),
                last_accessed=entry.get("last_accessed"),
                access_count=entry.get("access_count", 0),
                explicit_importance=entry.get("importance", 1.0),
                memory_type=entry.get("category", "fact"),
                content=entry.get("content", ""),
            )
            scored.append((entry, factors.total))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
