"""
Session management for the JARVIS reasoning engine.
====================================================
Manages multiple conversation sessions with isolation, persistence,
and lifecycle management.

Each session maintains its own:
    - Conversation history
    - Context state
    - User preferences
    - Active task plan

Sessions can be created, paused, resumed, and archived.

Usage:
    manager = SessionManager(settings)
    session = manager.create_session("work")
    manager.set_active("work")
    session.add_message("user", "Hello")
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jarvis.config.settings import AISettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Session lifecycle status."""
    ACTIVE = auto()
    PAUSED = auto()
    ARCHIVED = auto()


@dataclass
class Session:
    """A single conversation session."""
    id: str
    name: str
    created_at: datetime
    last_active: datetime
    status: SessionStatus = SessionStatus.ACTIVE
    message_count: int = 0
    user_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return (utc_now() - self.created_at).total_seconds()

    @property
    def idle_seconds(self) -> float:
        return (utc_now() - self.last_active).total_seconds()

    def touch(self) -> None:
        """Update last active time."""
        self.last_active = utc_now()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "status": self.status.name,
            "message_count": self.message_count,
            "user_id": self.user_id,
            "metadata": self.metadata,
        }


class SessionManager:
    """Manages multiple conversation sessions.

    Provides session creation, switching, persistence, and cleanup.

    Example:
        manager = SessionManager(settings)
        session = manager.create_session("work_session")
        manager.set_active("work_session")
        # ... interact ...
        manager.archive("work_session")
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._sessions: dict[str, Session] = {}
        self._active_session_id: str | None = None
        self._storage_dir = Path(settings.api.base_url or ".") / "data" / "sessions"

    def create_session(
        self,
        name: str | None = None,
        user_id: str = "default",
        metadata: dict | None = None,
    ) -> Session:
        """Create a new conversation session.

        Args:
            name: Optional session name. Auto-generated if None.
            user_id: Owner of the session.
            metadata: Additional session metadata.

        Returns:
            The created Session object.
        """
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        display_name = name or f"Session {len(self._sessions) + 1}"

        session = Session(
            id=session_id,
            name=display_name,
            created_at=utc_now(),
            last_active=utc_now(),
            user_id=user_id,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session
        logger.info("Session created: %s (%s)", display_name, session_id)

        # Auto-activate if first session
        if self._active_session_id is None:
            self._active_session_id = session_id

        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str, name: str | None = None) -> Session:
        """Get an existing session or create one with the given ID."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.touch()
            return session
        # Create with specified ID
        session = Session(
            id=session_id,
            name=name or session_id,
            created_at=utc_now(),
            last_active=utc_now(),
        )
        self._sessions[session_id] = session
        return session

    def set_active(self, session_id: str) -> bool:
        """Set the active session.

        Args:
            session_id: Session to activate.

        Returns:
            True if the session exists and was activated.
        """
        if session_id in self._sessions:
            self._active_session_id = session_id
            self._sessions[session_id].touch()
            logger.info("Active session set to: %s", session_id)
            return True
        return False

    def get_active(self) -> Session | None:
        """Return the currently active session."""
        if self._active_session_id:
            return self._sessions.get(self._active_session_id)
        return None

    def list_sessions(
        self,
        user_id: str | None = None,
        status: SessionStatus | None = None,
    ) -> list[Session]:
        """List sessions with optional filters."""
        sessions = list(self._sessions.values())
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        if status:
            sessions = [s for s in sessions if s.status == status]
        return sorted(sessions, key=lambda s: s.last_active, reverse=True)

    def pause(self, session_id: str) -> bool:
        """Pause a session."""
        session = self._sessions.get(session_id)
        if session:
            session.status = SessionStatus.PAUSED
            return True
        return False

    def resume(self, session_id: str) -> bool:
        """Resume a paused session."""
        session = self._sessions.get(session_id)
        if session and session.status == SessionStatus.PAUSED:
            session.status = SessionStatus.ACTIVE
            session.touch()
            return True
        return False

    def archive(self, session_id: str) -> bool:
        """Archive a session."""
        session = self._sessions.get(session_id)
        if session:
            session.status = SessionStatus.ARCHIVED
            if self._active_session_id == session_id:
                self._active_session_id = None
            logger.info("Session archived: %s", session_id)
            return True
        return False

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._active_session_id == session_id:
                self._active_session_id = None
            return True
        return False

    def cleanup_old(self, max_idle_seconds: float = 3600 * 24) -> int:
        """Archive sessions idle for too long.

        Args:
            max_idle_seconds: Maximum idle time before archival.

        Returns:
            Number of sessions archived.
        """
        archived = 0
        for session in list(self._sessions.values()):
            if (
                session.status == SessionStatus.ACTIVE
                and session.idle_seconds > max_idle_seconds
            ):
                self.archive(session.id)
                archived += 1

        if archived:
            logger.info("Auto-archived %d idle sessions", archived)
        return archived

    def get_stats(self) -> dict:
        """Return session management statistics."""
        active = sum(1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE)
        paused = sum(1 for s in self._sessions.values() if s.status == SessionStatus.PAUSED)
        archived = sum(1 for s in self._sessions.values() if s.status == SessionStatus.ARCHIVED)
        return {
            "total": len(self._sessions),
            "active": active,
            "paused": paused,
            "archived": archived,
            "active_session_id": self._active_session_id,
        }


from enum import Enum, auto  # needed for SessionStatus
