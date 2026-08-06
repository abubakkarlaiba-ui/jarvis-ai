"""
Skill: Notes
===========
Store, search, and manage notes with JSON persistence.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

NOTES_PATH = Path("./data/notes/notes.json")


def _load_notes(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_notes(path: Path, notes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotesSkill(BaseSkill):
    metadata = SkillMetadata(
        name="notes",
        version="1.0.0",
        description="Store, search, and manage notes",
        author="JARVIS Team",
        tags=["notes", "text", "storage"],
    )

    async def on_initialize(self) -> None:
        NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not NOTES_PATH.exists():
            _save_notes(NOTES_PATH, [])

    async def execute(self, context: SkillContext) -> SkillResult:
        action = context.parameters.get("action", "").lower()
        if not action:
            action = context.user_input.strip().split()[0] if context.user_input.strip() else ""

        handlers: dict[str, Any] = {
            "add": self._add,
            "list": self._list,
            "search": self._search,
            "delete": self._delete,
            "update": self._update,
        }

        handler = handlers.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {', '.join(handlers)}",
            )
        return await handler(context)

    async def _add(self, context: SkillContext) -> SkillResult:
        title = context.parameters.get("title", "")
        content = context.parameters.get("content", "")
        tags = context.parameters.get("tags", [])

        if not title and context.user_input.strip():
            title = context.user_input.strip()

        if not title:
            return SkillResult(success=False, error="A note title is required.")

        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        now = _now_iso()
        note = {
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "content": content,
            "tags": tags,
            "created": now,
            "modified": now,
        }

        notes = _load_notes(NOTES_PATH)
        notes.append(note)
        _save_notes(NOTES_PATH, notes)

        return SkillResult(
            success=True,
            output=f"Note '{title}' saved (id: {note['id']}).",
            metadata={"note": note},
        )

    async def _list(self, context: SkillContext) -> SkillResult:
        notes = _load_notes(NOTES_PATH)
        if not notes:
            return SkillResult(success=True, output="No notes stored.")

        lines = [f"[{n['id']}] {n['title']} (tags: {', '.join(n['tags'])})" for n in notes]
        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"count": len(notes)},
        )

    async def _search(self, context: SkillContext) -> SkillResult:
        query = context.parameters.get("query", context.user_input.strip()).lower()
        if not query:
            return SkillResult(success=False, error="A search query is required.")

        notes = _load_notes(NOTES_PATH)
        matches = [
            n for n in notes
            if query in n["title"].lower()
            or query in n["content"].lower()
            or any(query in t.lower() for t in n["tags"])
        ]

        if not matches:
            return SkillResult(success=True, output="No matching notes found.")

        lines = [f"[{n['id']}] {n['title']}: {n['content'][:80]}" for n in matches]
        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"count": len(matches)},
        )

    async def _delete(self, context: SkillContext) -> SkillResult:
        note_id = context.parameters.get("id", "").strip()
        if not note_id:
            return SkillResult(success=False, error="A note id is required.")

        notes = _load_notes(NOTES_PATH)
        new_notes = [n for n in notes if n["id"] != note_id]

        if len(new_notes) == len(notes):
            return SkillResult(success=False, error=f"Note '{note_id}' not found.")

        _save_notes(NOTES_PATH, new_notes)
        return SkillResult(success=True, output=f"Note '{note_id}' deleted.")

    async def _update(self, context: SkillContext) -> SkillResult:
        note_id = context.parameters.get("id", "").strip()
        if not note_id:
            return SkillResult(success=False, error="A note id is required.")

        notes = _load_notes(NOTES_PATH)
        for note in notes:
            if note["id"] == note_id:
                if "title" in context.parameters:
                    note["title"] = context.parameters["title"]
                if "content" in context.parameters:
                    note["content"] = context.parameters["content"]
                if "tags" in context.parameters:
                    tags = context.parameters["tags"]
                    note["tags"] = [t.strip() for t in tags.split(",") if t.strip()] if isinstance(tags, str) else tags
                note["modified"] = _now_iso()
                _save_notes(NOTES_PATH, notes)
                return SkillResult(
                    success=True,
                    output=f"Note '{note_id}' updated.",
                    metadata={"note": note},
                )

        return SkillResult(success=False, error=f"Note '{note_id}' not found.")
