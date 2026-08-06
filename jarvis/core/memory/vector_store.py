"""
Vector store engine for JARVIS memory.
======================================
Provides embedding generation, storage, and similarity search.

Supports multiple backends:
    - NumPy flat index (default, no dependencies)
    - FAISS index (optional, faster for large datasets)
    - In-memory fallback (smallest footprint)

Embeddings are generated via the OpenAI API or a local model.

Usage:
    store = VectorStore(settings)
    await store.initialize()
    await store.add("User prefers dark mode", metadata={"type": "preference"})
    results = await store.search("display preferences", top_k=5)
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from jarvis.config.settings import MemorySettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class VectorEntry:
    """A single entry in the vector store."""
    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    importance: float = 1.0
    access_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> VectorEntry:
        return cls(
            id=data["id"],
            text=data["text"],
            embedding=data["embedding"],
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", ""),
            importance=data.get("importance", 1.0),
            access_count=data.get("access_count", 0),
        )


@dataclass
class SearchResult:
    """A search result with relevance score."""
    entry: VectorEntry
    score: float
    match_type: str = "vector"  # vector, keyword, hybrid

    @property
    def relevance(self) -> float:
        return self.score


class EmbeddingGenerator:
    """Generates text embeddings via API or local model."""

    def __init__(self, api_key: str | None = None, model: str = "text-embedding-3-small", base_url: str | None = None):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._client = None

    async def initialize(self) -> None:
        """Initialize the embedding client."""
        if self._api_key:
            try:
                from openai import AsyncOpenAI
                kwargs = {"api_key": self._api_key}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._client = AsyncOpenAI(**kwargs)
                logger.info("Embedding generator initialized (model=%s)", self._model)
            except ImportError:
                logger.warning("openai not installed, using numpy fallback embeddings")
        else:
            logger.info("No API key for embeddings, using numpy fallback")

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text."""
        if self._client:
            return await self._embed_openai(text)
        return self._embed_fallback(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if self._client and len(texts) > 1:
            return await self._embed_openai_batch(texts)
        return [await self.embed(t) for t in texts]

    async def _embed_openai(self, text: str) -> list[float]:
        """Generate embedding via OpenAI API."""
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.error("Embedding generation failed: %s", exc)
            return self._embed_fallback(text)

    async def _embed_openai_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch via OpenAI API."""
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            logger.error("Batch embedding failed: %s", exc)
            return [self._embed_fallback(t) for t in texts]

    @staticmethod
    def _embed_fallback(text: str) -> list[float]:
        """Deterministic fallback embedding using hashing.

        Produces a consistent 384-dim vector from text content.
        Not semantically meaningful but useful for testing/fallback.
        """
        import hashlib
        # Use multiple hash seeds for better distribution
        dim = 384
        embedding = []
        for i in range(dim):
            h = hashlib.sha256(f"{text}_{i}".encode()).hexdigest()
            # Convert hex to float in [-1, 1]
            val = (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1
            embedding.append(val)
        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        return embedding


class VectorIndex:
    """In-memory vector index with cosine similarity search."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._vectors: np.ndarray | None = None
        self._ids: list[str] = []
        self._entries: dict[str, VectorEntry] = {}

    def add(self, entry: VectorEntry) -> None:
        """Add an entry to the index."""
        vec = np.array(entry.embedding, dtype=np.float32)
        if self._vectors is None:
            self._vectors = vec.reshape(1, -1)
        else:
            # Ensure dimension match
            if len(vec) != self._vectors.shape[1]:
                logger.warning("Embedding dimension mismatch: expected %d, got %d", self._vectors.shape[1], len(vec))
                return
            self._vectors = np.vstack([self._vectors, vec.reshape(1, -1)])
        self._ids.append(entry.id)
        self._entries[entry.id] = entry

    def remove(self, entry_id: str) -> bool:
        """Remove an entry from the index."""
        if entry_id not in self._entries:
            return False
        idx = self._ids.index(entry_id)
        self._ids.pop(idx)
        del self._entries[entry_id]
        if self._vectors is not None and len(self._vectors) > 0:
            self._vectors = np.delete(self._vectors, idx, axis=0)
            if self._vectors.shape[0] == 0:
                self._vectors = None
        return True

    def search(self, query_embedding: list[float], top_k: int = 10) -> list[tuple[str, float]]:
        """Find the top_k most similar entries by cosine similarity.

        Returns:
            List of (entry_id, similarity_score) tuples.
        """
        if self._vectors is None or len(self._vectors) == 0:
            return []

        query = np.array(query_embedding, dtype=np.float32)
        if len(query) != self._vectors.shape[1]:
            # Dimension mismatch — try truncating or padding
            if len(query) > self._vectors.shape[1]:
                query = query[:self._vectors.shape[1]]
            else:
                query = np.pad(query, (0, self._vectors.shape[1] - len(query)))

        # Cosine similarity via dot product (vectors are L2-normalized)
        query_norm = query / (np.linalg.norm(query) + 1e-10)
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True) + 1e-10
        normalized = self._vectors / norms
        similarities = normalized @ query_norm

        # Get top_k indices
        top_k = min(top_k, len(self._ids))
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            results.append((self._ids[idx], float(similarities[idx])))

        return results

    def save(self, path: Path) -> None:
        """Persist the index to disk."""
        data = {
            "dimension": self.dimension,
            "entries": [e.to_dict() for e in self._entries.values()],
        }
        path.write_text(json.dumps(data, default=str), encoding="utf-8")

    def load(self, path: Path) -> None:
        """Load the index from disk."""
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.dimension = data.get("dimension", self.dimension)
            for item in data.get("entries", []):
                entry = VectorEntry.from_dict(item)
                self.add(entry)
            logger.info("Vector index loaded: %d entries", len(self._entries))
        except Exception as exc:
            logger.error("Failed to load vector index: %s", exc)

    @property
    def size(self) -> int:
        return len(self._entries)


class VectorStore:
    """High-level vector store with embedding generation and persistence.

    Combines the embedding generator and vector index into a single
    interface for storing and retrieving memories by semantic similarity.

    Example:
        store = VectorStore(settings)
        await store.initialize()
        await store.add("User prefers dark mode", tags=["preference"])
        results = await store.search("what display settings does the user like")
    """

    def __init__(self, settings: MemorySettings):
        self._settings = settings
        self._storage_path = Path(settings.vector_store_path)
        self._index_file = self._storage_path / "index.json"

        self._generator: EmbeddingGenerator | None = None
        self._index: VectorIndex = VectorIndex(dimension=settings.embedding_dimension)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the vector store."""
        ensure_directory(self._storage_path)

        from jarvis.config.settings import get_settings
        root_settings = get_settings()

        self._generator = EmbeddingGenerator(
            api_key=root_settings.ai.api_key,
            model=root_settings.ai.embedding_model,
            base_url=root_settings.ai.base_url,
        )
        await self._generator.initialize()

        # Load existing index
        self._index.load(self._index_file)
        self._initialized = True
        logger.info("VectorStore initialized (%d entries)", self._index.size)

    async def add(
        self,
        text: str,
        entry_id: str | None = None,
        metadata: dict | None = None,
        importance: float = 1.0,
    ) -> VectorEntry:
        """Add a text entry to the vector store.

        Args:
            text: Text content to store.
            entry_id: Optional ID (auto-generated if None).
            metadata: Additional metadata.
            importance: Importance score (0-1).

        Returns:
            The created VectorEntry.
        """
        embedding = await self._generator.embed(text)

        entry = VectorEntry(
            id=entry_id or str(uuid.uuid4()),
            text=text,
            embedding=embedding,
            metadata=metadata or {},
            timestamp=utc_now().isoformat(),
            importance=importance,
        )

        self._index.add(entry)
        self._save()

        logger.debug("VectorStore: added '%s' (id=%s)", text[:50], entry.id)
        return entry

    async def add_batch(
        self,
        texts: list[str],
        metadata: list[dict] | None = None,
        importance: float = 1.0,
    ) -> list[VectorEntry]:
        """Add multiple texts in a batch (more efficient)."""
        embeddings = await self._generator.embed_batch(texts)

        entries = []
        for i, (text, emb) in enumerate(zip(texts, embeddings)):
            meta = metadata[i] if metadata and i < len(metadata) else {}
            entry = VectorEntry(
                id=str(uuid.uuid4()),
                text=text,
                embedding=emb,
                metadata=meta,
                timestamp=utc_now().isoformat(),
                importance=importance,
            )
            self._index.add(entry)
            entries.append(entry)

        self._save()
        return entries

    async def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
        filter_metadata: dict | None = None,
    ) -> list[SearchResult]:
        """Search for similar entries.

        Args:
            query: Search query text.
            top_k: Maximum results.
            min_score: Minimum similarity score.
            filter_metadata: Filter by metadata key-value pairs.

        Returns:
            List of SearchResult objects sorted by relevance.
        """
        query_embedding = await self._generator.embed(query)
        raw_results = self._index.search(query_embedding, top_k=top_k * 2)

        results = []
        for entry_id, score in raw_results:
            if score < min_score:
                continue
            entry = self._index._entries.get(entry_id)
            if not entry:
                continue
            # Apply metadata filter
            if filter_metadata:
                match = all(entry.metadata.get(k) == v for k, v in filter_metadata.items())
                if not match:
                    continue
            # Boost by importance
            adjusted_score = score * entry.importance
            results.append(SearchResult(entry=entry, score=adjusted_score))
            # Update access stats
            entry.access_count += 1

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def remove(self, entry_id: str) -> bool:
        """Remove an entry by ID."""
        success = self._index.remove(entry_id)
        if success:
            self._save()
        return success

    def _save(self) -> None:
        """Persist the index to disk."""
        if self._initialized:
            self._index.save(self._index_file)

    async def save_async(self) -> None:
        """Async save (call periodically)."""
        self._save()

    def get_entry(self, entry_id: str) -> VectorEntry | None:
        return self._index._entries.get(entry_id)

    def list_all(self, limit: int = 100) -> list[VectorEntry]:
        """List all entries (for debugging/admin)."""
        entries = list(self._index._entries.values())
        return entries[:limit]

    @property
    def size(self) -> int:
        return self._index.size
