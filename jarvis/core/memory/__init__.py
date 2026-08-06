"""
JARVIS Memory module.
=====================
Layered memory system with short-term, long-term, vector search,
preferences, projects, notes, reminders, and conversation archives.

Quick Start:
    from jarvis.core.memory import MemorySystem
    system = MemorySystem(settings)
    await system.initialize()
    await system.search("user preferences")
"""

from jarvis.core.memory.memory_system import MemorySystem
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

__all__ = [
    "MemorySystem",
    "ConversationManager",
    "LongTermMemory",
    "MemoryEntry",
    "MemoryVectorStore",
    "UserPreferences",
    "UserPreference",
    "ProjectMemory",
    "ProjectFact",
    "NoteManager",
    "Note",
    "ReminderManager",
    "Reminder",
    "ConversationArchiver",
    "MemoryCleanup",
    "CleanupStats",
    "MemoryBackup",
    "MemorySearchEngine",
    "MemorySearchResult",
    "ContextInjector",
]
