"""
User preferences store for JARVIS.
===================================
Persistent key-value store for user preferences with categories,
defaults, and conflict resolution.

Preferences are automatically injected into conversation context
so JARVIS always knows the user's settings and preferences.

Usage:
    prefs = PreferenceStore(settings)
    await prefs.initialize()
    await prefs.set("theme", "dark", category="display")
    theme = await prefs.get("theme", default="light")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jarvis.config.settings import MemorySettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class Preference:
    """A single user preference."""
    key: str
    value: Any
    category: str = "general"
    created_at: str = ""
    updated_at: str = ""
    source: str = "user"  # user, inferred, system
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Preference:
        return cls(**data)


# Default preferences that JARVIS starts with
DEFAULT_PREFERENCES: dict[str, dict] = {
    "response_style": {"value": "concise", "category": "communication"},
    "verbosity": {"value": "normal", "category": "communication"},
    "formality": {"value": "professional", "category": "communication"},
    "timezone": {"value": "UTC", "category": "system"},
    "theme": {"value": "dark", "category": "display"},
    "language": {"value": "en", "category": "system"},
    "units": {"value": "metric", "category": "system"},
}


class PreferenceStore:
    """Persistent user preference storage.

    Preferences are organized by category and support:
        - Get/set with defaults
        - Bulk operations
        - Inferred preferences (from behavior)
        - Import/export

    Example:
        store = PreferenceStore(settings)
        await store.initialize()
        await store.set("theme", "dark", category="display")
        all_prefs = await store.get_category("display")
    """

    def __init__(self, settings: MemorySettings):
        self._storage_path = Path(settings.preferences_file)
        self._preferences: dict[str, Preference] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Load preferences from disk."""
        ensure_directory(self._storage_path.parent)

        # Load existing preferences
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text(encoding="utf-8"))
                for item in data:
                    pref = Preference.from_dict(item)
                    self._preferences[pref.key] = pref
                logger.info("Loaded %d preferences", len(self._preferences))
            except Exception as exc:
                logger.error("Failed to load preferences: %s", exc)

        # Apply defaults for missing keys
        for key, defaults in DEFAULT_PREFERENCES.items():
            if key not in self._preferences:
                self._preferences[key] = Preference(
                    key=key,
                    value=defaults["value"],
                    category=defaults.get("category", "general"),
                    created_at=utc_now().isoformat(),
                    updated_at=utc_now().isoformat(),
                    source="system",
                )

        self._initialized = True
        self._save()

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a preference value.

        Args:
            key: Preference key.
            default: Value to return if not set.

        Returns:
            The preference value, or the default.
        """
        pref = self._preferences.get(key)
        if pref:
            pref.confidence = min(1.0, pref.confidence + 0.01)
            return pref.value
        return default

    async def set(
        self,
        key: str,
        value: Any,
        category: str = "general",
        source: str = "user",
        confidence: float = 1.0,
    ) -> Preference:
        """Set a preference value.

        Args:
            key: Preference key.
            value: Value to store.
            category: Category label.
            source: Source (user, inferred, system).
            confidence: Confidence in this preference (0-1).

        Returns:
            The created/updated Preference.
        """
        now = utc_now().isoformat()
        existing = self._preferences.get(key)

        if existing:
            existing.value = value
            existing.updated_at = now
            existing.source = source
            existing.confidence = confidence
            if category != "general":
                existing.category = category
            pref = existing
        else:
            pref = Preference(
                key=key,
                value=value,
                category=category,
                created_at=now,
                updated_at=now,
                source=source,
                confidence=confidence,
            )
            self._preferences[key] = pref

        self._save()
        logger.debug("Preference set: %s = %s (cat=%s)", key, str(value)[:50], category)
        return pref

    async def get_category(self, category: str) -> dict[str, Any]:
        """Get all preferences in a category.

        Returns:
            Dict of key → value for the category.
        """
        return {
            p.key: p.value
            for p in self._preferences.values()
            if p.category == category
        }

    async def get_all(self) -> dict[str, Any]:
        """Get all preferences as a flat dict."""
        return {p.key: p.value for p in self._preferences.values()}

    async def get_all_detailed(self) -> list[dict]:
        """Get all preferences with full metadata."""
        return [p.to_dict() for p in self._preferences.values()]

    async def delete(self, key: str) -> bool:
        """Delete a preference."""
        if key in self._preferences:
            del self._preferences[key]
            self._save()
            return True
        return False

    async def search(self, query: str) -> list[Preference]:
        """Search preferences by key or value."""
        query_lower = query.lower()
        return [
            p for p in self._preferences.values()
            if query_lower in p.key.lower() or query_lower in str(p.value).lower()
        ]

    async def infer_preference(self, key: str, value: Any, confidence: float = 0.7) -> Preference:
        """Record an inferred preference (from user behavior).

        Only updates if confidence is higher than existing.
        """
        existing = self._preferences.get(key)
        if existing and existing.confidence > confidence:
            return existing
        return await self.set(key, value, source="inferred", confidence=confidence)

    def _save(self) -> None:
        """Persist to disk."""
        data = [p.to_dict() for p in self._preferences.values()]
        self._storage_path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def to_context_string(self) -> str:
        """Format preferences for context injection."""
        lines = ["User preferences:"]
        by_category: dict[str, list[str]] = {}
        for p in self._preferences.values():
            if p.category not in by_category:
                by_category[p.category] = []
            by_category[p.category].append(f"  {p.key}: {p.value}")
        for cat, items in sorted(by_category.items()):
            lines.append(f"[{cat}]")
            lines.extend(items)
        return "\n".join(lines)

    @property
    def count(self) -> int:
        return len(self._preferences)
