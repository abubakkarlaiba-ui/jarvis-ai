"""
Memory routes — query and manage JARVIS memory.
================================================
Provides endpoints for:
    - Storing and retrieving memories
    - Searching across all memory sources
    - Managing preferences, projects, notes, reminders
    - Backup/restore operations
    - Memory cleanup and statistics
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────

class MemoryStoreRequest(BaseModel):
    """Request to store a memory."""
    content: str = Field(..., min_length=1, description="Content to remember")
    category: str = Field(default="general", description="Memory category")
    importance: float = Field(default=1.0, ge=0.0, le=5.0, description="Importance score")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class MemorySearchRequest(BaseModel):
    """Request to search memories."""
    query: str = Field(..., min_length=1, description="Search query")
    sources: list[str] | None = Field(default=None, description="Filter by sources")
    limit: int = Field(default=10, ge=1, le=100, description="Max results")


class PreferenceRequest(BaseModel):
    """Request to set a preference."""
    key: str = Field(..., min_length=1, description="Preference key")
    value: str = Field(..., description="Preference value")
    category: str = Field(default="general", description="Preference category")


class NoteRequest(BaseModel):
    """Request to create/update a note."""
    title: str = Field(..., min_length=1, description="Note title")
    content: str = Field(..., description="Note content")
    category: str = Field(default="general", description="Note category")
    tags: list[str] = Field(default_factory=list, description="Tags")


class ReminderRequest(BaseModel):
    """Request to create a reminder."""
    title: str = Field(..., min_length=1, description="Reminder title")
    description: str = Field(default="", description="Reminder description")
    due_at: str = Field(..., description="Due date/time (ISO format)")
    category: str = Field(default="general", description="Reminder category")
    priority: int = Field(default=1, ge=0, le=5, description="Priority (0=low, 5=urgent)")
    recurring: str | None = Field(default=None, description="Recurrence pattern")


class ProjectRequest(BaseModel):
    """Request to create/update a project."""
    name: str = Field(..., min_length=1, description="Project name")
    description: str = Field(default="", description="Project description")
    facts: list[str] = Field(default_factory=list, description="Facts to add")


# ──────────────────────────────────────────────
# Response Models
# ──────────────────────────────────────────────

class MemorySearchResultResponse(BaseModel):
    """A single search result."""
    content: str
    source: str
    score: float
    memory_id: str
    category: str
    timestamp: str
    importance: float


class MemorySearchResponse(BaseModel):
    """Response containing search results."""
    results: list[MemorySearchResultResponse]
    total: int
    query: str


class MemoryStatsResponse(BaseModel):
    """Memory usage statistics."""
    initialized: bool
    short_term_messages: int
    long_term: dict | None = None
    preferences: dict | None = None
    projects: dict | None = None
    notes: dict | None = None
    reminders: dict | None = None
    vector_store: dict | None = None


class BackupResponse(BaseModel):
    """Backup operation response."""
    success: bool
    backup_id: str = ""
    message: str = ""


# ──────────────────────────────────────────────
# Core Memory Routes
# ──────────────────────────────────────────────

@router.post("/store")
async def store_memory(request: MemoryStoreRequest) -> dict:
    """Store a new memory entry."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()

    entry = await core.memory_system.long_term.add(
        content=request.content,
        category=request.category,
        importance=request.importance,
        metadata=request.metadata,
    )
    return {"success": True, "entry_id": entry.id}


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest) -> MemorySearchResponse:
    """Search across all memory sources."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()

    results = await core.memory_system.search(
        query=request.query,
        sources=request.sources,
        limit=request.limit,
    )

    return MemorySearchResponse(
        results=[
            MemorySearchResultResponse(
                content=r.content,
                source=r.source,
                score=r.score,
                memory_id=r.memory_id,
                category=r.category,
                timestamp=r.timestamp,
                importance=r.importance,
            )
            for r in results
        ],
        total=len(results),
        query=request.query,
    )


@router.get("/stats", response_model=MemoryStatsResponse)
async def memory_stats() -> MemoryStatsResponse:
    """Return memory usage statistics."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    stats = await core.memory_system.get_stats()
    return MemoryStatsResponse(**stats)


# ──────────────────────────────────────────────
# Preferences Routes
# ──────────────────────────────────────────────

@router.get("/preferences")
async def get_preferences(category: str | None = None) -> dict:
    """Get all user preferences."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    prefs = await core.memory_system.preferences.get_all(category)
    return {"preferences": [p.to_dict() for p in prefs]}


@router.post("/preferences")
async def set_preference(request: PreferenceRequest) -> dict:
    """Set a user preference."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    await core.memory_system.preferences.set(
        key=request.key,
        value=request.value,
        category=request.category,
    )
    return {"success": True}


@router.delete("/preferences/{key}")
async def delete_preference(key: str) -> dict:
    """Delete a user preference."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    deleted = await core.memory_system.preferences.delete(key)
    return {"success": deleted}


# ──────────────────────────────────────────────
# Projects Routes
# ──────────────────────────────────────────────

@router.get("/projects")
async def list_projects() -> dict:
    """List all projects."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    projects = await core.memory_system.projects.list_projects()
    return {"projects": projects}


@router.post("/projects")
async def create_project(request: ProjectRequest) -> dict:
    """Create or update a project."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    await core.memory_system.projects.add_project(
        name=request.name,
        description=request.description,
    )
    for fact in request.facts:
        await core.memory_system.projects.add_fact(
            project_name=request.name,
            content=fact,
        )
    return {"success": True}


@router.get("/projects/{name}/context")
async def get_project_context(name: str) -> dict:
    """Get context for a specific project."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    context = await core.memory_system.projects.get_project_context(name)
    return {"context": context}


# ──────────────────────────────────────────────
# Notes Routes
# ──────────────────────────────────────────────

@router.get("/notes")
async def list_notes(
    category: str | None = None,
    tag: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """List notes with optional filters."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    notes = await core.memory_system.notes.list_notes(category, tag, limit)
    return {"notes": [n.to_dict() for n in notes]}


@router.post("/notes")
async def create_note(request: NoteRequest) -> dict:
    """Create a new note."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    note = await core.memory_system.notes.create(
        title=request.title,
        content=request.content,
        category=request.category,
        tags=request.tags,
    )
    return {"success": True, "note_id": note.id}


@router.delete("/notes/{note_id}")
async def delete_note(note_id: str) -> dict:
    """Delete a note."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    deleted = await core.memory_system.notes.delete(note_id)
    return {"success": deleted}


# ──────────────────────────────────────────────
# Reminders Routes
# ──────────────────────────────────────────────

@router.get("/reminders")
async def list_reminders(
    include_completed: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """List reminders."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    reminders = await core.memory_system.reminders.list_all(include_completed, limit)
    return {"reminders": [r.to_dict() for r in reminders]}


@router.get("/reminders/due")
async def get_due_reminders() -> dict:
    """Get reminders that are due now."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    due = await core.memory_system.reminders.get_due()
    return {"reminders": [r.to_dict() for r in due]}


@router.post("/reminders")
async def create_reminder(request: ReminderRequest) -> dict:
    """Create a new reminder."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    from datetime import datetime
    reminder = await core.memory_system.reminders.create(
        title=request.title,
        description=request.description,
        due_at=datetime.fromisoformat(request.due_at),
        category=request.category,
        priority=request.priority,
        recurring=request.recurring,
    )
    return {"success": True, "reminder_id": reminder.id}


@router.post("/reminders/{reminder_id}/complete")
async def complete_reminder(reminder_id: str) -> dict:
    """Mark a reminder as completed."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    completed = await core.memory_system.reminders.complete(reminder_id)
    return {"success": completed}


# ──────────────────────────────────────────────
# Backup Routes
# ──────────────────────────────────────────────

@router.post("/backup")
async def create_backup(label: str = "") -> BackupResponse:
    """Create a backup of all memory data."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    backup_id = await core.memory_system.create_backup(label)
    return BackupResponse(
        success=bool(backup_id),
        backup_id=backup_id,
        message="Backup created" if backup_id else "Backup failed",
    )


@router.get("/backup/list")
async def list_backups() -> dict:
    """List all available backups."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    backups = await core.memory_system._backup.list_backups()
    return {"backups": backups}


@router.post("/backup/restore/{backup_id}")
async def restore_backup(backup_id: str) -> dict:
    """Restore memory from a backup."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    success = await core.memory_system._backup.restore_backup(backup_id)
    return {"success": success, "message": "Restored" if success else "Restore failed"}


# ──────────────────────────────────────────────
# Cleanup Route
# ──────────────────────────────────────────────

@router.post("/cleanup")
async def run_cleanup() -> dict:
    """Run memory cleanup cycle."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    stats = await core.memory_system.run_cleanup()
    return {"stats": stats.to_dict()}
