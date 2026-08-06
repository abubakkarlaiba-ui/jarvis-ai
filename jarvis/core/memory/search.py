"""
Hybrid memory search engine for JARVIS.
=========================================
Combines vector similarity search with keyword matching for
fast, accurate retrieval across all memory types.

Search pipeline:
    1. Vector search (semantic similarity)
    2. Keyword search (BM25-style matching)
    3. Hybrid scoring (weighted combination)
    4. Result merging and deduplication
    5. Re-ranking by importance and recency

Usage:
    engine = MemorySearchEngine(settings)
    results = await engine.search("user prefers dark mode", memory_system)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from jarvis.config.settings import MemorySettings

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """Search configuration parameters."""
    max_results: int = 20
    min_relevance: float = 0.3
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    enable_hybrid: bool = True
    boost_importance: float = 0.2
    boost_recency: float = 0.1


@dataclass
class MemorySearchResult:
    """A unified search result from any memory type."""
    content: str
    source: str  # short_term, long_term, vector, preference, project, note, reminder, conversation
    score: float
    memory_id: str = ""
    category: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: str = ""
    importance: float = 1.0

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "source": self.source,
            "score": round(self.score, 4),
            "memory_id": self.memory_id,
            "category": self.category,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "importance": self.importance,
        }


class KeywordScorer:
    """BM25-inspired keyword scoring for text search."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._avg_doc_len = 100.0
        self._doc_count = 0

    def score(self, query: str, document: str) -> float:
        """Score a document against a query using BM25-inspired scoring."""
        query_words = query.lower().split()
        doc_words = document.lower().split()
        doc_len = len(doc_words)

        if not query_words or not doc_words:
            return 0.0

        score = 0.0
        for q_word in query_words:
            tf = doc_words.count(q_word)
            if tf == 0:
                continue

            # Term frequency with saturation
            tf_norm = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self._avg_doc_len))
            score += tf_norm

        # Normalize by query length
        return score / len(query_words) if query_words else 0.0

    def update_stats(self, avg_doc_len: float, doc_count: int) -> None:
        self._avg_doc_len = avg_doc_len
        self._doc_count = doc_count


class MemorySearchEngine:
    """Hybrid search engine across all memory types.

    Combines vector similarity with keyword matching for optimal
    retrieval from short-term, long-term, vector, preferences,
    projects, notes, reminders, and conversation archives.

    Example:
        engine = MemorySearchEngine(settings)
        results = await engine.search("weather preferences", memory_system)
        for r in results:
            print(f"[{r.source}] {r.content[:60]} (score={r.score:.3f})")
    """

    def __init__(self, settings: MemorySettings):
        self._config = SearchConfig(
            max_results=settings.search_max_results,
            min_relevance=settings.search_min_relevance,
            vector_weight=settings.search_vector_weight,
            keyword_weight=1.0 - settings.search_vector_weight,
            enable_hybrid=settings.search_enable_hybrid,
        )
        self._keyword_scorer = KeywordScorer()

    async def search(
        self,
        query: str,
        memory_system: Any = None,
        sources: list[str] | None = None,
        limit: int | None = None,
    ) -> list[MemorySearchResult]:
        """Search across all memory sources.

        Args:
            query: Search query.
            memory_system: The MemorySystem instance.
            sources: Filter to specific sources (None = all).
            limit: Override max results.

        Returns:
            List of MemorySearchResult sorted by score.
        """
        if not memory_system:
            return []

        limit = limit or self._config.max_results
        all_results: list[MemorySearchResult] = []

        # 1. Vector search (most important for semantic queries)
        if self._config.enable_hybrid and memory_system.vector_store:
            try:
                vector_results = await memory_system.vector_store.search(
                    query, top_k=limit * 2, min_score=0.1
                )
                for vr in vector_results:
                    all_results.append(MemorySearchResult(
                        content=vr.entry.text,
                        source="vector",
                        score=vr.score * self._config.vector_weight,
                        memory_id=vr.entry.id,
                        category=vr.entry.metadata.get("category", ""),
                        metadata=vr.entry.metadata,
                        timestamp=vr.entry.timestamp,
                        importance=vr.entry.importance,
                    ))
            except Exception as exc:
                logger.debug("Vector search failed: %s", exc)

        # 2. Long-term memory (keyword search)
        if memory_system.long_term and (not sources or "long_term" in sources):
            try:
                ltm_results = memory_system.long_term.search_facts(query, limit=limit)
                for fact in ltm_results:
                    kw_score = self._keyword_scorer.score(query, fact.content)
                    all_results.append(MemorySearchResult(
                        content=fact.content,
                        source="long_term",
                        score=kw_score * self._config.keyword_weight,
                        memory_id=fact.id,
                        category=fact.category,
                        timestamp=fact.created_at.isoformat(),
                        importance=fact.confidence,
                    ))
            except Exception as exc:
                logger.debug("Long-term search failed: %s", exc)

        # 3. Notes search
        if memory_system.notes and (not sources or "notes" in sources):
            try:
                notes = await memory_system.notes.search(query, limit=limit)
                for note in notes:
                    kw_score = self._keyword_scorer.score(query, note.title + " " + note.content)
                    all_results.append(MemorySearchResult(
                        content=f"{note.title}: {note.content[:200]}",
                        source="notes",
                        score=kw_score * self._config.keyword_weight,
                        memory_id=note.id,
                        category=note.category,
                        timestamp=note.updated_at,
                    ))
            except Exception as exc:
                logger.debug("Notes search failed: %s", exc)

        # 4. Preferences search
        if memory_system.preferences and (not sources or "preferences" in sources):
            try:
                prefs = await memory_system.preferences.search(query)
                for pref in prefs:
                    score = 0.8 if query.lower() in pref.key.lower() else 0.4
                    all_results.append(MemorySearchResult(
                        content=f"{pref.key}: {pref.value}",
                        source="preferences",
                        score=score,
                        memory_id=pref.key,
                        category=pref.category,
                    ))
            except Exception as exc:
                logger.debug("Preferences search failed: %s", exc)

        # 5. Project memory search
        if memory_system.projects and (not sources or "projects" in sources):
            try:
                projects = await memory_system.projects.list_projects()
                for proj in projects:
                    facts = await memory_system.projects.search(proj["name"], query, limit=5)
                    for fact in facts:
                        kw_score = self._keyword_scorer.score(query, fact.content)
                        all_results.append(MemorySearchResult(
                            content=f"[{proj['name']}] {fact.content}",
                            source="projects",
                            score=kw_score * self._config.keyword_weight,
                            memory_id=fact.id,
                            category=fact.category,
                            metadata={"project": proj["name"]},
                            importance=fact.importance,
                        ))
            except Exception as exc:
                logger.debug("Project search failed: %s", exc)

        # Merge and deduplicate
        merged = self._merge_results(all_results)

        # Filter by minimum relevance
        merged = [r for r in merged if r.score >= self._config.min_relevance]

        # Sort by score
        merged.sort(key=lambda r: r.score, reverse=True)

        return merged[:limit]

    def _merge_results(self, results: list[MemorySearchResult]) -> list[MemorySearchResult]:
        """Merge duplicate results, keeping the highest score."""
        seen: dict[str, MemorySearchResult] = {}
        for result in results:
            key = result.content[:100]  # dedup by content prefix
            if key in seen:
                if result.score > seen[key].score:
                    seen[key] = result
            else:
                seen[key] = result
        return list(seen.values())

    def format_results(self, results: list[MemorySearchResult]) -> str:
        """Format search results as a readable string."""
        if not results:
            return "No relevant memories found."

        lines = [f"Found {len(results)} relevant memories:"]
        for i, r in enumerate(results[:10], 1):
            source_tag = f"[{r.source}]"
            lines.append(f"  {i}. {source_tag} {r.content[:100]} (score={r.score:.3f})")
        return "\n".join(lines)
