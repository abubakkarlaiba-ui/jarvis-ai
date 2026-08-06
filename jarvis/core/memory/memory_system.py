"""
Unified memory system orchestrator for JARVIS.
================================================
Wires together all memory subsystems into a single, cohesive API surface.

Subsystems:
    - Short-term memory (session context)
    - Long-term memory (facts with decay)
    - Vector store (semantic search)
    - Preferences (user settings)
    - Projects (per-project knowledge)
    - Notes (structured user notes)
    - Reminders (time-based alerts)
    - Conversations (interaction archive)
    - Cleanup (pruning/maintenance)
    - Backup (export/import)
    - Search (hybrid retrieval)
    - Context (auto-injection)

Usage:
    system = MemorySystem(settings)
    await system.initialize()
    await system.save("fact", "User likes Python", "long_term")
    results = await system.search("programming preferences")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from jarvis.config.settings import MemorySettings, AISettings
from jarvis.core.memory.conversation_manager import ConversationManager
from jarvis.core.memory.long_term import LongTermMemory, MemoryEntry
from jarvis.core.memory.vector_store import VectorStore as MemoryVectorStore
from jarvis.core.memory.preferences import PreferenceStore as UserPreferences, Preference as UserPreference
from jarvis.core.memory.projects import ProjectMemoryStore as ProjectMemory, ProjectFact
from jarvis.core.memory.notes import NoteStore as NoteManager, Note
from jarvis.core.memory.reminders import ReminderStore as ReminderManager, Reminder
from jarvis.core.memory.conversations import ConversationArchive as ConversationArchiver
from jarvis.core.memory.cleanup import MemoryCleanup, CleanupStats
from jarvis.core.memory.backup import MemoryBackup
from jarvis.core.memory.search import MemorySearchEngine, MemorySearchResult
from jarvis.core.memory.context_injector import ContextInjector

logger = logging.getLogger(__name__)


class MemorySystem:
    """Unified memory system for JARVIS.

    Provides a single interface to all memory subsystems while
    maintaining the individual APIs for specialized operations.

    Example:
        system = MemorySystem(settings)
        await system.initialize()

        # Save a memory
        entry = MemoryEntry(
            content="User prefers Python over JavaScript",
            category="user_preference",
            importance=1.2,
        )
        await system.long_term.add(entry)

        # Search across all sources
        results = await system.search("programming language preference")

        # Get context for LLM injection
        context = await system.get_context("code review", "session-1")
    """

    def __init__(self, memory_settings: MemorySettings, ai_settings: AISettings | None = None):
        self._settings = memory_settings
        self._ai_settings = ai_settings

        # Subsystem instances (created in initialize())
        self.short_term: ConversationManager | None = None
        self.long_term: LongTermMemory | None = None
        self.vector_store: MemoryVectorStore | None = None
        self.preferences: UserPreferences | None = None
        self.projects: ProjectMemory | None = None
        self.notes: NoteManager | None = None
        self.reminders: ReminderManager | None = None
        self.conversations: ConversationArchiver | None = None

        # Utility subsystems
        self._cleanup: MemoryCleanup | None = None
        self._backup: MemoryBackup | None = None
        self._search: MemorySearchEngine | None = None
        self._context_injector: ContextInjector | None = None

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all memory subsystems."""
        if self._initialized:
            return

        logger.info("Initializing memory system...")

        # Core memory
        self.short_term = ConversationManager(
            max_messages=self._settings.short_term_max_messages,
            summary_threshold=self._settings.short_term_summary_threshold,
            window_size=self._settings.conversation_window_size,
        )
        self.long_term = LongTermMemory(self._settings)
        await self.long_term.initialize()

        self.vector_store = MemoryVectorStore(self._settings)
        self.preferences = UserPreferences(self._settings)
        await self.preferences.initialize()

        self.projects = ProjectMemory(self._settings)
        await self.projects.initialize()

        self.notes = NoteManager(self._settings)
        await self.notes.initialize()

        self.reminders = ReminderManager(self._settings)
        await self.reminders.initialize()

        self.conversations = ConversationArchiver(self._settings)
        await self.conversations.initialize()

        # Utilities
        self._cleanup = MemoryCleanup(self._settings)
        self._backup = MemoryBackup(self._settings)
        self._search = MemorySearchEngine(self._settings)
        self._context_injector = ContextInjector(self._settings, self._ai_settings)

        self._initialized = True
        logger.info("Memory system initialized successfully")

    async def shutdown(self) -> None:
        """Clean shutdown of all subsystems."""
        logger.info("Shutting down memory system...")
        if self.conversations:
            await self.conversations.close()
        self._initialized = False

    async def search(
        self,
        query: str,
        sources: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        """Search across all memory sources.

        Args:
            query: Search query.
            sources: Filter to specific sources (None = all).
            limit: Max results to return.

        Returns:
            List of MemorySearchResult sorted by relevance.
        """
        return await self._search.search(query, self, sources, limit)

    async def get_context(self, query: str, session_id: str) -> str:
        """Build a context block for LLM injection.

        Args:
            query: The user's current message.
            session_id: Current session ID.

        Returns:
            Formatted context block string.
        """
        return await self._context_injector.build_context(query, session_id, self)

    async def get_conversation_context(self, session_id: str) -> str:
        """Get recent conversation summary for context injection."""
        if self.short_term:
            return self.short_term.get_summary()
        return ""

    async def run_cleanup(self) -> CleanupStats:
        """Run a memory cleanup cycle."""
        all_memories = await self._get_all_memory_entries()
        return await self._cleanup.run_cleanup(all_memories)

    async def create_backup(self, label: str = "") -> str:
        """Create a backup of all memory data."""
        return await self._backup.create_backup(label)

    async def get_stats(self) -> dict:
        """Get memory system statistics."""
        stats = {
            "initialized": self._initialized,
            "short_term_messages": self.short_term.get_message_count() if self.short_term else 0,
        }

        if self.long_term:
            ltm_stats = await self.long_term.get_stats()
            stats["long_term"] = ltm_stats

        if self.preferences:
            pref_stats = await self.preferences.get_stats()
            stats["preferences"] = pref_stats

        if self.projects:
            proj_stats = await self.projects.get_stats()
            stats["projects"] = proj_stats

        if self.notes:
            note_stats = await self.notes.get_stats()
            stats["notes"] = note_stats

        if self.reminders:
            reminder_stats = await self.reminders.get_stats()
            stats["reminders"] = reminder_stats

        if self.vector_store:
            vec_stats = await self.vector_store.get_stats()
            stats["vector_store"] = vec_stats

        return stats

    async def _get_all_memory_entries(self) -> list[dict]:
        """Collect all memory entries for cleanup."""
        entries = []
        if self.long_term:
            facts = await self.long_term.get_all()
            for f in facts:
                entries.append({
                    "id": f.id,
                    "content": f.content,
                    "category": f.category,
                    "importance": f.confidence,
                    "created_at": f.created_at.isoformat(),
                    "last_accessed": f.last_accessed.isoformat() if f.last_accessed else None,
                    "access_count": f.access_count,
                })
        return entries
