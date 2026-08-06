"""
Notes store for JARVIS.
========================
Structured note storage with tagging, search, and organization.

Notes are persistent, searchable, and can be linked to projects
or conversations.

Usage:
    notes = NoteStore(settings)
    await notes.initialize()
    await notes.create("API Design", content="Use REST with /v1/ prefix", tags=["api", "design"])
    results = await notes.search("API design patterns")
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
class Note:
    """A single note."""
    id: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    project: str = ""
    created_at: str = ""
    updated_at: str = ""
    pinned: bool = False
    archived: bool = False
    linked_conversation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "category": self.category,
            "project": self.project,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pinned": self.pinned,
            "archived": self.archived,
            "linked_conversation": self.linked_conversation,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Note:
        return cls(**data)


class NoteStore:
    """Persistent note storage with full-text search.

    Example:
        store = NoteStore(settings)
        await store.initialize()
        await store.create("Meeting Notes", "Discussed API v2 timeline", tags=["meeting"])
        results = await store.search("API timeline")
    """

    def __init__(self, settings: MemorySettings):
        self._storage_dir = Path(settings.notes_dir)
        self._max_notes = settings.max_notes
        self._notes: dict[str, Note] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Load notes from disk."""
        ensure_directory(self._storage_dir)
        notes_file = self._storage_dir / "notes.json"
        if notes_file.exists():
            try:
                data = json.loads(notes_file.read_text(encoding="utf-8"))
                for item in data:
                    note = Note.from_dict(item)
                    self._notes[note.id] = note
                logger.info("Loaded %d notes", len(self._notes))
            except Exception as exc:
                logger.error("Failed to load notes: %s", exc)
        self._initialized = True

    async def create(
        self,
        title: str,
        content: str = "",
        tags: list[str] | None = None,
        category: str = "general",
        project: str = "",
        pinned: bool = False,
    ) -> Note:
        """Create a new note.

        Args:
            title: Note title.
            content: Note content (markdown supported).
            tags: Tags for categorization.
            category: Category label.
            project: Linked project name.
            pinned: Whether to pin the note.

        Returns:
            The created Note.
        """
        # Enforce limit
        if len(self._notes) >= self._max_notes:
            # Remove oldest unpinned note
            unpinned = [n for n in self._notes.values() if not n.pinned]
            if unpinned:
                oldest = min(unpinned, key=lambda n: n.created_at)
                del self._notes[oldest.id]

        now = utc_now().isoformat()
        note = Note(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            tags=tags or [],
            category=category,
            project=project,
            created_at=now,
            updated_at=now,
            pinned=pinned,
        )
        self._notes[note.id] = note
        self._save()
        logger.debug("Note created: '%s'", title[:50])
        return note

    async def get(self, note_id: str) -> Note | None:
        """Get a note by ID."""
        return self._notes.get(note_id)

    async def update(
        self,
        note_id: str,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
        pinned: bool | None = None,
    ) -> Note | None:
        """Update a note."""
        note = self._notes.get(note_id)
        if not note:
            return None
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        if tags is not None:
            note.tags = tags
        if category is not None:
            note.category = category
        if pinned is not None:
            note.pinned = pinned
        note.updated_at = utc_now().isoformat()
        self._save()
        return note

    async def delete(self, note_id: str) -> bool:
        """Delete a note."""
        if note_id in self._notes:
            del self._notes[note_id]
            self._save()
            return True
        return False

    async def search(
        self,
        query: str,
        tags: list[str] | None = None,
        category: str | None = None,
        project: str | None = None,
        include_archived: bool = False,
        limit: int = 20,
    ) -> list[Note]:
        """Search notes by content, title, and tags.

        Args:
            query: Search text.
            tags: Filter by tags (AND logic).
            category: Filter by category.
            project: Filter by project.
            include_archived: Include archived notes.
            limit: Maximum results.

        Returns:
            Matching notes sorted by relevance.
        """
        query_lower = query.lower()
        words = set(query_lower.split()) if query_lower else set()

        results: list[tuple[float, Note]] = []
        for note in self._notes.values():
            if not include_archived and note.archived:
                continue
            if category and note.category != category:
                continue
            if project and note.project != project:
                continue
            if tags and not all(t in note.tags for t in tags):
                continue

            # Score: title match (3x), tag match (2x), content match (1x)
            score = 0.0
            title_lower = note.title.lower()
            content_lower = note.content.lower()

            for w in words:
                if w in title_lower:
                    score += 3.0
                if w in content_lower:
                    score += 1.0
                if any(w in t.lower() for t in note.tags):
                    score += 2.0

            if note.pinned:
                score += 0.5

            if score > 0:
                results.append((score, note))

        results.sort(key=lambda x: x[0], reverse=True)
        return [note for _, note in results[:limit]]

    async def list_recent(self, limit: int = 20) -> list[Note]:
        """Get most recently updated notes."""
        notes = sorted(self._notes.values(), key=lambda n: n.updated_at, reverse=True)
        return [n for n in notes if not n.archived][:limit]

    async def list_pinned(self) -> list[Note]:
        """Get all pinned notes."""
        return [n for n in self._notes.values() if n.pinned and not n.archived]

    async def list_by_project(self, project: str) -> list[Note]:
        """Get all notes for a project."""
        return [n for n in self._notes.values() if n.project == project and not n.archived]

    async def archive(self, note_id: str) -> bool:
        """Archive a note."""
        note = self._notes.get(note_id)
        if note:
            note.archived = True
            note.updated_at = utc_now().isoformat()
            self._save()
            return True
        return False

    def _save(self) -> None:
        notes_file = self._storage_dir / "notes.json"
        data = [n.to_dict() for n in self._notes.values()]
        notes_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    @property
    def count(self) -> int:
        return len([n for n in self._notes.values() if not n.archived])
