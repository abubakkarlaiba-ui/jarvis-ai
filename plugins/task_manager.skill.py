"""
Skill: Task Manager
===================
Track tasks with priorities, due dates, tags, and status filtering.
Persists data as JSON in ./data/tasks/tasks.json.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

TASKS_PATH = Path("./data/tasks/tasks.json")

VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"pending", "in-progress", "done"}

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_tasks(path: Path, tasks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_due(date_str: str) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _is_overdue(task: dict[str, Any]) -> bool:
    if task.get("status") == "done":
        return False
    due = _parse_due(task.get("due_date", ""))
    if due is None:
        return False
    now = datetime.now(timezone.utc)
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return due < now


class TaskManagerSkill(BaseSkill):
    metadata = SkillMetadata(
        name="task_manager",
        version="1.0.0",
        description="Task management with priorities, due dates, tags, and filtering",
        author="JARVIS Team",
        tags=["tasks", "todo", "productivity", "project"],
    )

    async def on_initialize(self) -> None:
        TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not TASKS_PATH.exists():
            _save_tasks(TASKS_PATH, [])

    async def execute(self, context: SkillContext) -> SkillResult:
        action = context.parameters.get("action", "").lower()
        if not action and context.user_input.strip():
            action = context.user_input.strip().split()[0].lower()

        handlers: dict[str, Any] = {
            "add": self._add,
            "list": self._list,
            "update": self._update,
            "delete": self._delete,
            "search": self._search,
            "stats": self._stats,
        }

        handler = handlers.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {', '.join(handlers)}",
            )
        return await handler(context)

    async def _add(self, context: SkillContext) -> SkillResult:
        title = context.parameters.get("title", "").strip()
        if not title:
            return SkillResult(success=False, error="A task title is required.")

        description = context.parameters.get("description", "")
        priority = context.parameters.get("priority", "medium").lower()
        due_date = context.parameters.get("due_date", "")
        tags = context.parameters.get("tags", [])

        if priority not in VALID_PRIORITIES:
            return SkillResult(
                success=False,
                error=f"Invalid priority '{priority}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}",
            )

        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        now = _now_iso()
        task = {
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "description": description,
            "priority": priority,
            "status": "pending",
            "due_date": due_date,
            "tags": tags,
            "created": now,
            "modified": now,
        }

        tasks = _load_tasks(TASKS_PATH)
        tasks.append(task)
        _save_tasks(TASKS_PATH, tasks)

        return SkillResult(
            success=True,
            output=f"Task '{title}' created (id: {task['id']}, priority: {priority}).",
            metadata={"task": task},
        )

    async def _list(self, context: SkillContext) -> SkillResult:
        tasks = _load_tasks(TASKS_PATH)
        if not tasks:
            return SkillResult(success=True, output="No tasks.")

        status_filter = context.parameters.get("status", "").lower()
        priority_filter = context.parameters.get("priority", "").lower()
        tags_filter = context.parameters.get("tags", "")
        sort_by = context.parameters.get("sort", "priority").lower()

        if status_filter:
            tasks = [t for t in tasks if t.get("status") == status_filter]
        if priority_filter:
            tasks = [t for t in tasks if t.get("priority") == priority_filter]
        if tags_filter:
            filter_tags = [t.strip().lower() for t in tags_filter.split(",") if t.strip()]
            tasks = [
                t for t in tasks
                if any(ft in [tag.lower() for tag in t.get("tags", [])] for ft in filter_tags)
            ]

        if sort_by == "priority":
            tasks.sort(key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium"), 99))
        elif sort_by == "due":
            tasks.sort(key=lambda t: t.get("due_date", "") or "9999")

        lines = []
        for t in tasks:
            marker = "X" if t["status"] == "done" else ">" if t["status"] == "in-progress" else " "
            overdue = " [OVERDUE]" if _is_overdue(t) else ""
            due = f" due:{t['due_date']}" if t.get("due_date") else ""
            tags_str = f" ({', '.join(t['tags'])})" if t.get("tags") else ""
            lines.append(
                f"[{marker}] {t['id']} | {t['title']} | {t['priority']}{due}{tags_str}{overdue}"
            )

        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"count": len(tasks), "total_all": len(_load_tasks(TASKS_PATH))},
        )

    async def _update(self, context: SkillContext) -> SkillResult:
        task_id = context.parameters.get("id", "").strip()
        if not task_id:
            return SkillResult(success=False, error="A task id is required.")

        tasks = _load_tasks(TASKS_PATH)
        for task in tasks:
            if task["id"] == task_id:
                if "title" in context.parameters:
                    task["title"] = context.parameters["title"]
                if "description" in context.parameters:
                    task["description"] = context.parameters["description"]
                if "priority" in context.parameters:
                    p = context.parameters["priority"].lower()
                    if p not in VALID_PRIORITIES:
                        return SkillResult(
                            success=False,
                            error=f"Invalid priority '{p}'. Must be: {', '.join(sorted(VALID_PRIORITIES))}",
                        )
                    task["priority"] = p
                if "status" in context.parameters:
                    s = context.parameters["status"].lower()
                    if s not in VALID_STATUSES:
                        return SkillResult(
                            success=False,
                            error=f"Invalid status '{s}'. Must be: {', '.join(sorted(VALID_STATUSES))}",
                        )
                    task["status"] = s
                if "due_date" in context.parameters:
                    task["due_date"] = context.parameters["due_date"]
                if "tags" in context.parameters:
                    tags = context.parameters["tags"]
                    task["tags"] = (
                        [t.strip() for t in tags.split(",") if t.strip()]
                        if isinstance(tags, str)
                        else tags
                    )
                task["modified"] = _now_iso()
                _save_tasks(TASKS_PATH, tasks)
                return SkillResult(
                    success=True,
                    output=f"Task '{task_id}' updated.",
                    metadata={"task": task},
                )

        return SkillResult(success=False, error=f"Task '{task_id}' not found.")

    async def _delete(self, context: SkillContext) -> SkillResult:
        task_id = context.parameters.get("id", "").strip()
        if not task_id:
            return SkillResult(success=False, error="A task id is required.")

        tasks = _load_tasks(TASKS_PATH)
        new_tasks = [t for t in tasks if t["id"] != task_id]

        if len(new_tasks) == len(tasks):
            return SkillResult(success=False, error=f"Task '{task_id}' not found.")

        _save_tasks(TASKS_PATH, new_tasks)
        return SkillResult(success=True, output=f"Task '{task_id}' deleted.")

    async def _search(self, context: SkillContext) -> SkillResult:
        query = context.parameters.get("query", context.user_input.strip()).lower()
        if not query:
            return SkillResult(success=False, error="A search query is required.")

        tasks = _load_tasks(TASKS_PATH)
        matches = [
            t for t in tasks
            if query in t["title"].lower()
            or query in t.get("description", "").lower()
            or any(query in tag.lower() for tag in t.get("tags", []))
        ]

        if not matches:
            return SkillResult(success=True, output="No matching tasks found.")

        lines = [
            f"[{t['id']}] {t['title']} | {t['priority']} | {t['status']}"
            for t in matches
        ]
        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"count": len(matches)},
        )

    async def _stats(self, context: SkillContext) -> SkillResult:
        tasks = _load_tasks(TASKS_PATH)
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("status") == "done")
        in_progress = sum(1 for t in tasks if t.get("status") == "in-progress")
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        overdue = sum(1 for t in tasks if _is_overdue(t))

        by_priority = {}
        for p in VALID_PRIORITIES:
            by_priority[p] = sum(1 for t in tasks if t.get("priority") == p)

        output = (
            f"Total: {total} | Pending: {pending} | In Progress: {in_progress} | "
            f"Done: {completed} | Overdue: {overdue}\n"
            f"By Priority: {', '.join(f'{k}:{v}' for k, v in sorted(by_priority.items(), key=lambda x: PRIORITY_ORDER[x[0]]))}"
        )

        return SkillResult(
            success=True,
            output=output,
            metadata={
                "total": total,
                "completed": completed,
                "in_progress": in_progress,
                "pending": pending,
                "overdue": overdue,
                "by_priority": by_priority,
            },
        )
