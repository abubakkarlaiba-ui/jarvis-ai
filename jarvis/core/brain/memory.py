"""
Conversation memory system for the JARVIS reasoning engine.
==========================================================
Three-tier memory architecture:

    Short-Term Memory  — last N messages (in-memory, fast access)
    Working Memory     — active context window (what the LLM sees right now)
    Long-Term Memory   — persisted facts, preferences, and past conversations

The memory system automatically manages transitions between tiers:
    - Old short-term entries are summarized and moved to long-term
    - Relevant long-term memories are injected into working memory
    -重要 facts are extracted and persisted permanently

Usage:
    memory = ConversationMemory(settings)
    await memory.initialize()
    await memory.add_message(session_id, "user", "What's the weather?")
    context = await memory.get_context(session_id)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

from jarvis.config.settings import AISettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """Roles in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A single conversation message."""
    id: str
    role: MessageRole
    content: str
    timestamp: datetime
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    emotion: str | None = None
    summary: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        d = {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "token_count": self.token_count,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            token_count=data.get("token_count", 0),
            metadata=data.get("metadata", {}),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
        )

    @classmethod
    def create(cls, role: MessageRole, content: str, **kwargs) -> Message:
        """Factory method to create a new message with defaults."""
        return cls(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=utc_now(),
            **kwargs,
        )


@dataclass
class Fact:
    """An extracted fact stored in long-term memory."""
    id: str
    content: str
    category: str
    confidence: float
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    source_session: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
        }


class ShortTermMemory:
    """Fixed-capacity rolling buffer of recent messages.

    This is the primary source for constructing the LLM context window.
    Messages older than the capacity are automatically summarized and
    moved to long-term memory.
    """

    def __init__(self, max_messages: int = 50):
        self.max_messages = max_messages
        self._messages: deque[Message] = deque(maxlen=max_messages)

    def add(self, message: Message) -> list[Message]:
        """Add a message. Returns any evicted messages that need summarizing."""
        evicted = []
        if len(self._messages) == self.max_messages:
            # Capture messages that will be evicted
            evict_count = max(1, self.max_messages // 5)
            for _ in range(evict_count):
                if self._messages:
                    evicted.append(self._messages.popleft())
        self._messages.append(message)
        return evicted

    def get_recent(self, n: int | None = None) -> list[Message]:
        """Return the most recent n messages, or all if n is None."""
        msgs = list(self._messages)
        if n is not None:
            return msgs[-n:]
        return msgs

    def get_working_window(self, max_tokens: int = 8000) -> list[Message]:
        """Return messages that fit within a token budget.

        Starts from the most recent and works backward, including as
        many messages as the token budget allows.
        """
        selected = []
        token_count = 0
        for msg in reversed(self._messages):
            est_tokens = msg.token_count or self._estimate_tokens(msg.content)
            if token_count + est_tokens > max_tokens:
                break
            selected.insert(0, msg)
            token_count += est_tokens
        return selected

    def clear(self) -> None:
        self._messages.clear()

    @property
    def size(self) -> int:
        return len(self._messages)

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate (1 token ≈ 4 chars for English)."""
        return max(1, len(text) // 4)


class LongTermMemory:
    """Persistent storage for facts, preferences, and conversation history.

    Backed by JSON files for simplicity. Swap for SQLite or a vector DB
    for production scale.
    """

    def __init__(self, storage_path: str):
        self._storage_path = Path(storage_path)
        ensure_directory(self._storage_path)

        self._facts: dict[str, Fact] = {}
        self._conversation_archive: list[dict] = []

        self._load()

    def _load(self) -> None:
        """Load persisted data from disk."""
        facts_file = self._storage_path / "facts.json"
        if facts_file.exists():
            try:
                data = json.loads(facts_file.read_text(encoding="utf-8"))
                for item in data:
                    fact = Fact(
                        id=item["id"],
                        content=item["content"],
                        category=item["category"],
                        confidence=item["confidence"],
                        created_at=datetime.fromisoformat(item["created_at"]),
                        last_accessed=datetime.fromisoformat(item["last_accessed"]),
                        access_count=item.get("access_count", 0),
                    )
                    self._facts[fact.id] = fact
                logger.debug("Loaded %d facts from long-term memory", len(self._facts))
            except Exception as exc:
                logger.error("Failed to load facts: %s", exc)

        archive_file = self._storage_path / "archive.json"
        if archive_file.exists():
            try:
                self._conversation_archive = json.loads(
                    archive_file.read_text(encoding="utf-8")
                )
            except Exception as exc:
                logger.error("Failed to load archive: %s", exc)

    def _save(self) -> None:
        """Persist data to disk."""
        facts_file = self._storage_path / "facts.json"
        facts_data = [f.to_dict() for f in self._facts.values()]
        facts_file.write_text(json.dumps(facts_data, indent=2), encoding="utf-8")

        archive_file = self._storage_path / "archive.json"
        archive_file.write_text(
            json.dumps(self._conversation_archive[-1000:], indent=2, default=str),
            encoding="utf-8",
        )

    def store_fact(
        self,
        content: str,
        category: str = "general",
        confidence: float = 0.8,
        source_session: str = "",
    ) -> Fact:
        """Store a fact in long-term memory."""
        now = utc_now()
        fact = Fact(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            confidence=confidence,
            created_at=now,
            last_accessed=now,
            source_session=source_session,
        )
        self._facts[fact.id] = fact
        self._save()
        logger.debug("Stored fact: '%s' (cat=%s, conf=%.2f)", content[:60], category, confidence)
        return fact

    def search_facts(self, query: str, limit: int = 10) -> list[Fact]:
        """Search facts by keyword matching.

        Args:
            query: Search terms.
            limit: Maximum results.

        Returns:
            Matching facts sorted by confidence and recency.
        """
        query_lower = query.lower()
        words = set(query_lower.split())

        scored: list[tuple[float, Fact]] = []
        for fact in self._facts.values():
            content_lower = fact.content.lower()
            # Simple word overlap scoring
            overlap = sum(1 for w in words if w in content_lower)
            if overlap == 0:
                continue
            score = (overlap / len(words)) * fact.confidence
            scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for _, fact in scored[:limit]:
            fact.last_accessed = utc_now()
            fact.access_count += 1
            results.append(fact)

        if results:
            self._save()

        return results

    def get_facts_by_category(self, category: str) -> list[Fact]:
        """Return all facts in a given category."""
        return [f for f in self._facts.values() if f.category == category]

    def archive_conversation(self, session_id: str, summary: str, messages: list[Message]) -> None:
        """Archive a completed conversation."""
        self._conversation_archive.append({
            "session_id": session_id,
            "summary": summary,
            "message_count": len(messages),
            "archived_at": utc_now().isoformat(),
        })
        self._save()

    def get_recent_archives(self, limit: int = 5) -> list[dict]:
        """Return recent conversation archives."""
        return self._conversation_archive[-limit:]

    @property
    def fact_count(self) -> int:
        return len(self._facts)

    @property
    def archive_count(self) -> int:
        return len(self._conversation_archive)


class ConversationMemory:
    """Unified memory interface for the reasoning engine.

    Coordinates short-term, working, and long-term memory to provide
    the reasoning engine with all the context it needs. Integrates
    with the new MemorySystem for enhanced capabilities.

    Example:
        memory = ConversationMemory(settings)
        await memory.initialize()
        await memory.add_message("session-1", "user", "My name is Tony")
        await memory.add_message("session-1", "assistant", "Hello, Tony!")
        context = await memory.get_context("session-1")
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._short_term: dict[str, ShortTermMemory] = {}  # per-session
        self._long_term: LongTermMemory | None = None
        self._memory_system: Any = None  # New MemorySystem integration
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize memory subsystems."""
        from jarvis.config.settings import BASE_DIR
        storage = str(BASE_DIR / "data" / "memory")
        self._long_term = LongTermMemory(storage)
        self._initialized = True
        logger.info("ConversationMemory initialized")

    async def initialize_with_memory_system(self, memory_system: Any) -> None:
        """Initialize with the new unified MemorySystem.

        This enables enhanced search, context injection, and all
        the new memory subsystems.

        Args:
            memory_system: The MemorySystem instance from memory_system.py.
        """
        self._memory_system = memory_system
        logger.info("ConversationMemory integrated with MemorySystem")

    def _get_short_term(self, session_id: str) -> ShortTermMemory:
        """Get or create short-term memory for a session."""
        if session_id not in self._short_term:
            self._short_term[session_id] = ShortTermMemory(
                max_messages=self._settings.max_tokens // 100  # rough estimate
            )
        return self._short_term[session_id]

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs,
    ) -> Message:
        """Add a message to conversation memory.

        Args:
            session_id: Session identifier.
            role: Message role (user, assistant, system, tool).
            content: Message content.
            **kwargs: Additional message metadata.

        Returns:
            The created Message object.
        """
        message = Message.create(
            role=MessageRole(role),
            content=content,
            token_count=ShortTermMemory._estimate_tokens(content),
            **kwargs,
        )

        st = self._get_short_term(session_id)
        evicted = st.add(message)

        # Summarize and archive evicted messages
        if evicted and self._settings.summarization_enabled:
            for msg in evicted:
                if msg.role == MessageRole.USER:
                    self._long_term.store_fact(
                        content=msg.content,
                        category="conversation_history",
                        confidence=0.6,
                        source_session=session_id,
                    )

        return message

    async def get_context(
        self,
        session_id: str,
        max_tokens: int = 8000,
        include_system: bool = True,
        query: str = "",
    ) -> list[Message]:
        """Build the working context window for a reasoning request.

        Combines:
            1. System message (if include_system)
            2. Relevant long-term facts (via context injector)
            3. Recent short-term messages

        Args:
            session_id: Session identifier.
            max_tokens: Maximum token budget.
            include_system: Whether to include a system context message.
            query: Current user message for context injection.

        Returns:
            List of Messages ready for LLM consumption.
        """
        context: list[Message] = []

        # Reserve tokens for system message and facts
        reserved = 500 if include_system else 0

        # System context with injected memories
        if include_system:
            system_content = "You are JARVIS, a professional AI assistant."

            # Inject relevant memories if MemorySystem is available
            if self._memory_system and query:
                try:
                    memory_context = await self._memory_system.get_context(query, session_id)
                    if memory_context:
                        from jarvis.core.memory.context_injector import ContextInjector
                        injector = ContextInjector.__new__(ContextInjector)
                        system_content = injector.format_for_prompt(memory_context) + system_content
                except Exception as exc:
                    logger.debug("Context injection failed: %s", exc)

            context.append(Message.create(
                role=MessageRole.SYSTEM,
                content=system_content,
            ))

        # Recent conversation
        st = self._get_short_term(session_id)
        budget = max_tokens - reserved
        recent = st.get_working_window(max_tokens=budget)
        context.extend(recent)

        return context

    async def add_tool_result(
        self,
        session_id: str,
        tool_call_id: str,
        content: str,
    ) -> Message:
        """Add a tool result message to memory."""
        return await self.add_message(
            session_id,
            "tool",
            content,
            tool_call_id=tool_call_id,
        )

    async def search_long_term(self, query: str, limit: int = 5) -> list[Fact]:
        """Search long-term memory for relevant facts."""
        if self._long_term:
            return self._long_term.search_facts(query, limit)
        return []

    async def store_fact(self, content: str, category: str = "general", **kwargs) -> Fact:
        """Store a fact in long-term memory."""
        if self._long_term:
            return self._long_term.store_fact(content, category, **kwargs)
        raise RuntimeError("Long-term memory not initialized")

    async def get_summary_context(self, session_id: str) -> str:
        """Get a summary of earlier conversation for context injection."""
        st = self._get_short_term(session_id)
        total = st.size
        working = min(total, 20)

        if total <= working:
            return ""

        # Messages outside the working window need summarizing
        older = st.get_recent(total - working)
        user_msgs = [m.content for m in older if m.role == MessageRole.USER]
        if not user_msgs:
            return ""

        # Simple extractive summary
        key_points = user_msgs[-5:]  # last 5 user messages from older set
        return "Earlier in this conversation: " + "; ".join(key_points)

    def clear_session(self, session_id: str) -> None:
        """Clear all memory for a session."""
        if session_id in self._short_term:
            self._short_term[session_id].clear()

    def get_stats(self, session_id: str | None = None) -> dict:
        """Return memory statistics."""
        stats = {
            "sessions": len(self._short_term),
            "ltm_facts": self._long_term.fact_count if self._long_term else 0,
            "ltm_archives": self._long_term.archive_count if self._long_term else 0,
        }
        if session_id and session_id in self._short_term:
            st = self._short_term[session_id]
            stats["session_messages"] = st.size
        return stats
