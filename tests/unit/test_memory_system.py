"""Unit tests for the memory subsystems."""

from __future__ import annotations

import pytest

from tests.conftest import run_async

from jarvis.config.settings import MemorySettings
from jarvis.core.memory.long_term import LongTermMemory, MemoryEntry
from jarvis.core.memory.preferences import PreferenceStore
from jarvis.core.memory.projects import ProjectMemoryStore
from jarvis.core.memory.notes import NoteStore
from jarvis.core.memory.reminders import ReminderStore
from jarvis.core.memory.conversations import ConversationArchive


def _make_settings(tmp_path) -> MemorySettings:
    return MemorySettings(
        data_dir=str(tmp_path / "memory"),
        preferences_file=str(tmp_path / "memory" / "preferences.json"),
        projects_dir=str(tmp_path / "memory" / "projects"),
        notes_dir=str(tmp_path / "memory" / "notes"),
        reminders_file=str(tmp_path / "memory" / "reminders.json"),
        archive_dir=str(tmp_path / "memory" / "conversations"),
    )


@pytest.mark.unit
class TestLongTermMemory:
    def test_add_memory(self, tmp_path):
        settings = _make_settings(tmp_path)
        ltm = LongTermMemory(settings)
        run_async(ltm.initialize())

        entry = run_async(ltm.add("User likes Python", category="preference"))
        assert entry.content == "User likes Python"
        assert entry.category == "preference"

    def test_search_memory(self, tmp_path):
        settings = _make_settings(tmp_path)
        ltm = LongTermMemory(settings)
        run_async(ltm.initialize())

        run_async(ltm.add("User prefers dark mode"))
        run_async(ltm.add("User likes cats"))
        results = run_async(ltm.search_facts("dark mode"))
        assert len(results) >= 1
        assert any("dark mode" in r.content for r in results)

    def test_delete_memory(self, tmp_path):
        settings = _make_settings(tmp_path)
        ltm = LongTermMemory(settings)
        run_async(ltm.initialize())

        entry = run_async(ltm.add("Temporary fact"))
        deleted = run_async(ltm.delete(entry.id))
        assert deleted is True
        remaining = run_async(ltm.get_all())
        assert all(e.id != entry.id for e in remaining)

    def test_list_memories(self, tmp_path):
        settings = _make_settings(tmp_path)
        ltm = LongTermMemory(settings)
        run_async(ltm.initialize())

        run_async(ltm.add("Fact one"))
        run_async(ltm.add("Fact two"))
        run_async(ltm.add("Fact three"))
        all_entries = run_async(ltm.get_all())
        assert len(all_entries) == 3

    def test_memory_importance(self, tmp_path):
        settings = _make_settings(tmp_path)
        ltm = LongTermMemory(settings)
        run_async(ltm.initialize())

        entry = run_async(ltm.add("Important fact", importance=2.5))
        retrieved = run_async(ltm.get(entry.id))
        assert retrieved is not None
        assert retrieved.confidence == 2.5

    def test_conversation_memory(self, tmp_path):
        settings = _make_settings(tmp_path)
        archive = ConversationArchive(settings)
        run_async(archive.initialize())

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        conv = run_async(archive.archive("session-1", messages, summary="Greeting exchange"))
        assert conv.session_id == "session-1"
        assert conv.message_count == 2


@pytest.mark.unit
class TestPreferences:
    def test_preferences_create(self, tmp_path):
        settings = _make_settings(tmp_path)
        prefs = PreferenceStore(settings)
        run_async(prefs.initialize())

        run_async(prefs.set("theme", "dark", category="display"))
        value = run_async(prefs.get("theme"))
        assert value == "dark"

    def test_preferences_update(self, tmp_path):
        settings = _make_settings(tmp_path)
        prefs = PreferenceStore(settings)
        run_async(prefs.initialize())

        run_async(prefs.set("theme", "dark"))
        run_async(prefs.set("theme", "light"))
        value = run_async(prefs.get("theme"))
        assert value == "light"

    def test_preferences_delete(self, tmp_path):
        settings = _make_settings(tmp_path)
        prefs = PreferenceStore(settings)
        run_async(prefs.initialize())

        run_async(prefs.set("temp_key", "temp_value"))
        deleted = run_async(prefs.delete("temp_key"))
        assert deleted is True
        value = run_async(prefs.get("temp_key"))
        assert value is None


@pytest.mark.unit
class TestProjects:
    def test_projects_create(self, tmp_path):
        settings = _make_settings(tmp_path)
        projects = ProjectMemoryStore(settings)
        run_async(projects.initialize())

        fact = run_async(projects.store("jarvis", "Using FastAPI", category="implementation"))
        assert fact.content == "Using FastAPI"

    def test_projects_search(self, tmp_path):
        settings = _make_settings(tmp_path)
        projects = ProjectMemoryStore(settings)
        run_async(projects.initialize())

        run_async(projects.store("jarvis", "FastAPI for REST API"))
        run_async(projects.store("jarvis", "SQLite for database"))
        results = run_async(projects.search("jarvis", "REST API"))
        assert len(results) >= 1

    def test_projects_delete(self, tmp_path):
        settings = _make_settings(tmp_path)
        projects = ProjectMemoryStore(settings)
        run_async(projects.initialize())

        fact = run_async(projects.store("jarvis", "Temporary note"))
        deleted = run_async(projects.delete_fact("jarvis", fact.id))
        assert deleted is True


@pytest.mark.unit
class TestNotes:
    def test_notes_create(self, tmp_path):
        settings = _make_settings(tmp_path)
        notes = NoteStore(settings)
        run_async(notes.initialize())

        note = run_async(notes.create("Meeting Notes", content="Discussed API v2"))
        assert note.title == "Meeting Notes"

    def test_notes_search(self, tmp_path):
        settings = _make_settings(tmp_path)
        notes = NoteStore(settings)
        run_async(notes.initialize())

        run_async(notes.create("API Design", content="Use REST with /v1/ prefix", tags=["api"]))
        results = run_async(notes.search("API"))
        assert len(results) >= 1

    def test_notes_delete(self, tmp_path):
        settings = _make_settings(tmp_path)
        notes = NoteStore(settings)
        run_async(notes.initialize())

        note = run_async(notes.create("Temp Note"))
        deleted = run_async(notes.delete(note.id))
        assert deleted is True


@pytest.mark.unit
class TestReminders:
    def test_reminders_create(self, tmp_path):
        settings = _make_settings(tmp_path)
        reminders = ReminderStore(settings)
        run_async(reminders.initialize())

        r = run_async(reminders.create("Check email", trigger_at="2099-01-15T09:00:00"))
        assert r.title == "Check email"

    def test_reminders_list(self, tmp_path):
        settings = _make_settings(tmp_path)
        reminders = ReminderStore(settings)
        run_async(reminders.initialize())

        run_async(reminders.create("Task 1", trigger_at="2099-01-15T09:00:00"))
        run_async(reminders.create("Task 2", trigger_at="2099-01-15T10:00:00"))
        all_reminders = run_async(reminders.list_all())
        assert len(all_reminders) == 2

    def test_reminders_delete(self, tmp_path):
        settings = _make_settings(tmp_path)
        reminders = ReminderStore(settings)
        run_async(reminders.initialize())

        r = run_async(reminders.create("Temp Reminder"))
        deleted = run_async(reminders.delete(r.id))
        assert deleted is True
