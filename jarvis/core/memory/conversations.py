"""
Conversation archive for JARVIS.
=================================
Stores complete conversation histories with full-text search,
summarization, and metadata extraction.

Usage:
    archive = ConversationArchive(settings)
    await archive.initialize()
    await archive.archive(session_id, messages, summary="Discussed API design")
    results = await archive.search("API design decisions")
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jarvis.config.settings import MemorySettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class ArchivedConversation:
    """A complete archived conversation."""
    id: str
    session_id: str
    summary: str
    message_count: int
    started_at: str
    archived_at: str
    topic: str = ""
    tags: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    messages: list[dict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "summary": self.summary,
            "message_count": self.message_count,
            "started_at": self.started_at,
            "archived_at": self.archived_at,
            "topic": self.topic,
            "tags": self.tags,
            "key_facts": self.key_facts,
            "sentiment": self.sentiment,
            "message_count": self.message_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ArchivedConversation:
        d = dict(data)
        d.pop("messages", None)  # Don't load messages into memory by default
        return cls(**d)


class ConversationArchive:
    """Persistent conversation storage with search.

    Conversations are stored as JSON files with metadata for fast search.
    Full message content is stored separately for deep search.

    Example:
        archive = ConversationArchive(settings)
        await archive.initialize()
        await archive.archive("session-1", messages, summary="Weather discussion")
        results = await archive.search("weather London")
    """

    def __init__(self, settings: MemorySettings):
        self._storage_dir = Path(settings.archive_dir)
        self._max_size = settings.max_archive_size
        self._conversations: dict[str, ArchivedConversation] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Load conversation index from disk."""
        ensure_directory(self._storage_dir)
        index_file = self._storage_dir / "index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                for item in data:
                    conv = ArchivedConversation.from_dict(item)
                    self._conversations[conv.id] = conv
                logger.info("Loaded %d archived conversations", len(self._conversations))
            except Exception as exc:
                logger.error("Failed to load conversation index: %s", exc)
        self._initialized = True

    async def archive(
        self,
        session_id: str,
        messages: list[dict],
        summary: str = "",
        topic: str = "",
        tags: list[str] | None = None,
        key_facts: list[str] | None = None,
    ) -> ArchivedConversation:
        """Archive a conversation.

        Args:
            session_id: Original session ID.
            messages: List of message dicts with role and content.
            summary: Conversation summary.
            topic: Main topic.
            tags: Tags for categorization.
            key_facts: Important facts from the conversation.

        Returns:
            The ArchivedConversation.
        """
        # Enforce limit
        if len(self._conversations) >= self._max_size:
            oldest = min(self._conversations.values(), key=lambda c: c.archived_at)
            await self._delete_full(oldest.id)

        now = utc_now().isoformat()
        conv = ArchivedConversation(
            id=str(uuid.uuid4()),
            session_id=session_id,
            summary=summary,
            message_count=len(messages),
            started_at=messages[0].get("timestamp", now) if messages else now,
            archived_at=now,
            topic=topic,
            tags=tags or [],
            key_facts=key_facts or [],
            metadata={"source": "auto_archive"},
        )

        # Save messages to separate file
        messages_file = self._storage_dir / f"{conv.id}.json"
        messages_file.write_text(
            json.dumps(messages, indent=2, default=str),
            encoding="utf-8",
        )

        self._conversations[conv.id] = conv
        self._save_index()

        logger.info("Archived conversation: %s (%d messages)", conv.id, len(messages))
        return conv

    async def search(
        self,
        query: str,
        topic: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[ArchivedConversation]:
        """Search archived conversations.

        Args:
            query: Search text.
            topic: Filter by topic.
            tags: Filter by tags.
            limit: Maximum results.

        Returns:
            Matching conversations sorted by relevance.
        """
        query_lower = query.lower()
        words = set(query_lower.split())

        scored: list[tuple[float, ArchivedConversation]] = []
        for conv in self._conversations.values():
            if topic and conv.topic != topic:
                continue
            if tags and not any(t in conv.tags for t in tags):
                continue

            score = 0.0
            summary_lower = conv.summary.lower()
            for w in words:
                if w in summary_lower:
                    score += 2.0
                if any(w in f.lower() for f in conv.key_facts):
                    score += 1.5
                if w in conv.topic.lower():
                    score += 3.0

            if score > 0:
                scored.append((score, conv))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [conv for _, conv in scored[:limit]]

    async def get_messages(self, conversation_id: str) -> list[dict]:
        """Load full messages for a conversation."""
        messages_file = self._storage_dir / f"{conversation_id}.json"
        if messages_file.exists():
            return json.loads(messages_file.read_text(encoding="utf-8"))
        return []

    async def get_recent(self, limit: int = 10) -> list[ArchivedConversation]:
        """Get most recent archived conversations."""
        convs = sorted(self._conversations.values(), key=lambda c: c.archived_at, reverse=True)
        return convs[:limit]

    async def get_by_topic(self, topic: str) -> list[ArchivedConversation]:
        """Get all conversations on a topic."""
        return [c for c in self._conversations.values() if c.topic == topic]

    async def _delete_full(self, conv_id: str) -> None:
        """Delete a conversation and its messages file."""
        messages_file = self._storage_dir / f"{conv_id}.json"
        if messages_file.exists():
            messages_file.unlink()
        self._conversations.pop(conv_id, None)

    async def delete(self, conv_id: str) -> bool:
        if conv_id in self._conversations:
            await self._delete_full(conv_id)
            self._save_index()
            return True
        return False

    def _save_index(self) -> None:
        index_file = self._storage_dir / "index.json"
        data = [c.to_dict() for c in self._conversations.values()]
        index_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    @property
    def count(self) -> int:
        return len(self._conversations)
