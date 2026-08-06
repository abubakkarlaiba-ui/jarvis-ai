"""
Reminder system for JARVIS.
============================
Stores and manages time-based reminders with recurrence support.

Reminders are checked periodically and surfaced to the user
at the appropriate time.

Usage:
    reminders = ReminderStore(settings)
    await reminders.initialize()
    await reminders.create("Check email at 9am", trigger_at="2024-01-15T09:00:00")
    due = await reminders.get_due()
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

from jarvis.config.settings import MemorySettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


class ReminderRecurrence(Enum):
    """Recurrence patterns for reminders."""
    NONE = auto()
    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()
    YEARLY = auto()


@dataclass
class Reminder:
    """A single reminder."""
    id: str
    title: str
    description: str = ""
    trigger_at: str = ""  # ISO datetime
    recurrence: str = "none"
    category: str = "general"
    priority: str = "normal"  # low, normal, high, urgent
    created_at: str = ""
    triggered: bool = False
    dismissed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def trigger_datetime(self) -> datetime | None:
        if self.trigger_at:
            return datetime.fromisoformat(self.trigger_at)
        return None

    @property
    def is_due(self) -> bool:
        if self.dismissed or not self.trigger_at:
            return False
        trigger = self.trigger_datetime
        if trigger:
            return utc_now() >= trigger
        return False

    @property
    def is_overdue(self) -> bool:
        if not self.trigger_at:
            return False
        trigger = self.trigger_datetime
        if trigger and not self.dismissed:
            return utc_now() > trigger + timedelta(minutes=5)
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "trigger_at": self.trigger_at,
            "recurrence": self.recurrence,
            "category": self.category,
            "priority": self.priority,
            "created_at": self.created_at,
            "triggered": self.triggered,
            "dismissed": self.dismissed,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Reminder:
        return cls(**data)


class ReminderStore:
    """Persistent reminder storage with due checking.

    Example:
        store = ReminderStore(settings)
        await store.initialize()
        await store.create("Team meeting", trigger_at="2024-01-15T14:00:00", priority="high")
        due = await store.get_due()
    """

    def __init__(self, settings: MemorySettings):
        self._storage_path = Path(settings.reminders_file)
        self._reminders: dict[str, Reminder] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Load reminders from disk."""
        ensure_directory(self._storage_path.parent)
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text(encoding="utf-8"))
                for item in data:
                    r = Reminder.from_dict(item)
                    self._reminders[r.id] = r
                logger.info("Loaded %d reminders", len(self._reminders))
            except Exception as exc:
                logger.error("Failed to load reminders: %s", exc)
        self._initialized = True

    async def create(
        self,
        title: str,
        trigger_at: str = "",
        description: str = "",
        category: str = "general",
        priority: str = "normal",
        recurrence: str = "none",
        metadata: dict | None = None,
    ) -> Reminder:
        """Create a new reminder.

        Args:
            title: Reminder title.
            trigger_at: ISO datetime string for when to trigger.
            description: Detailed description.
            category: Category label.
            priority: Priority level (low, normal, high, urgent).
            recurrence: Recurrence pattern (none, daily, weekly, monthly, yearly).
            metadata: Additional metadata.

        Returns:
            The created Reminder.
        """
        now = utc_now().isoformat()
        reminder = Reminder(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            trigger_at=trigger_at,
            recurrence=recurrence,
            category=category,
            priority=priority,
            created_at=now,
            metadata=metadata or {},
        )
        self._reminders[reminder.id] = reminder
        self._save()
        logger.info("Reminder created: '%s' (trigger=%s)", title, trigger_at[:19] if trigger_at else "none")
        return reminder

    async def get_due(self) -> list[Reminder]:
        """Get all reminders that are currently due."""
        return [r for r in self._reminders.values() if r.is_due]

    async def get_upcoming(self, hours: int = 24) -> list[Reminder]:
        """Get reminders due within the next N hours."""
        now = utc_now()
        cutoff = now + timedelta(hours=hours)
        upcoming = []
        for r in self._reminders.values():
            if r.dismissed or not r.trigger_at:
                continue
            trigger = r.trigger_datetime
            if trigger and now <= trigger <= cutoff:
                upcoming.append(r)
        return sorted(upcoming, key=lambda r: r.trigger_at)

    async def dismiss(self, reminder_id: str) -> bool:
        """Dismiss a reminder."""
        r = self._reminders.get(reminder_id)
        if r:
            r.dismissed = True
            r.triggered = True
            # Handle recurrence
            if r.recurrence != "none":
                next_trigger = self._next_trigger(r)
                if next_trigger:
                    r.trigger_at = next_trigger.isoformat()
                    r.dismissed = False
                    r.triggered = False
            self._save()
            return True
        return False

    def _next_trigger(self, reminder: Reminder) -> datetime | None:
        """Calculate next trigger time for recurring reminders."""
        trigger = reminder.trigger_datetime
        if not trigger:
            return None
        rec = ReminderRecurrence[reminder.recurrence.upper()]
        if rec == ReminderRecurrence.DAILY:
            return trigger + timedelta(days=1)
        elif rec == ReminderRecurrence.WEEKLY:
            return trigger + timedelta(weeks=1)
        elif rec == ReminderRecurrence.MONTHLY:
            return trigger + timedelta(days=30)
        elif rec == ReminderRecurrence.YEARLY:
            return trigger + timedelta(days=365)
        return None

    async def delete(self, reminder_id: str) -> bool:
        """Delete a reminder."""
        if reminder_id in self._reminders:
            del self._reminders[reminder_id]
            self._save()
            return True
        return False

    async def list_all(self, include_dismissed: bool = False) -> list[Reminder]:
        """List all reminders."""
        reminders = list(self._reminders.values())
        if not include_dismissed:
            reminders = [r for r in reminders if not r.dismissed]
        return sorted(reminders, key=lambda r: r.trigger_at or "9999")

    async def search(self, query: str) -> list[Reminder]:
        """Search reminders by title or description."""
        query_lower = query.lower()
        return [
            r for r in self._reminders.values()
            if query_lower in r.title.lower() or query_lower in r.description.lower()
        ]

    def _save(self) -> None:
        data = [r.to_dict() for r in self._reminders.values()]
        self._storage_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    @property
    def active_count(self) -> int:
        return sum(1 for r in self._reminders.values() if not r.dismissed)

    @property
    def due_count(self) -> int:
        return sum(1 for r in self._reminders.values() if r.is_due)
