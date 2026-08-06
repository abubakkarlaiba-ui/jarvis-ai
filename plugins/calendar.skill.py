"""
Skill: Calendar
================
Manage calendar events using ICS files (iCalendar format).

Requires the ``icalendar`` package: pip install icalendar
Data is stored in ./data/calendar/events.ics.

If icalendar is not installed the skill degrades gracefully and
returns a clear error message.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from icalendar import Calendar, Event, vDatetime

    ICALENDAR_AVAILABLE = True
except ImportError:
    ICALENDAR_AVAILABLE = False

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

DEFAULT_ICS_PATH = "./data/calendar/events.ics"


def _calendar_path(context: SkillContext) -> Path:
    raw = context.parameters.get("ics_path", DEFAULT_ICS_PATH)
    return Path(raw).resolve()


def _ensure_calendar_file(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//JARVIS//Calendar Skill//EN\nEND:VCALENDAR\n", encoding="utf-8")


def _load_calendar(path: Path) -> Calendar:
    _ensure_calendar_file(path)
    return Calendar.from_ical(path.read_text(encoding="utf-8"))


def _save_calendar(cal: Calendar, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cal.to_ical())


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if hasattr(value, "dt"):
        return _parse_dt(value.dt)
    return None


def _format_event(event: Event, index: int) -> str:
    summary = str(event.get("SUMMARY", "Untitled"))
    dtstart = _parse_dt(event.get("DTSTART"))
    dtend = _parse_dt(event.get("DTEND"))
    location = str(event.get("LOCATION", ""))
    description = str(event.get("DESCRIPTION", ""))

    start_str = dtstart.strftime("%Y-%m-%d %H:%M") if dtstart else "TBD"
    end_str = dtend.strftime("%H:%M") if dtend else ""
    time_range = f"{start_str} – {end_str}" if end_str else start_str

    lines = [f"{index}. {summary}", f"   When: {time_range}"]
    if location:
        lines.append(f"   Where: {location}")
    if description:
        lines.append(f"   Notes: {description[:100]}")
    return "\n".join(lines)


def _find_free_slots(
    cal: Calendar,
    days_ahead: int = 7,
    slot_minutes: int = 60,
) -> list[str]:
    now = datetime.now(timezone.utc)
    end_window = now + timedelta(days=days_ahead)

    busy: list[tuple[datetime, datetime]] = []
    for comp in cal.walk("VEVENT"):
        start = _parse_dt(comp.get("DTSTART"))
        end = _parse_dt(comp.get("DTEND"))
        if start and end:
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if end > now and start < end_window:
                busy.append((start, end))
    busy.sort()

    free_slots: list[str] = []
    cursor = now
    slot_dur = timedelta(minutes=slot_minutes)

    for bs, be in busy:
        while cursor + slot_dur <= bs:
            free_slots.append(
                f"{cursor.strftime('%Y-%m-%d %H:%M')} – {(cursor + slot_dur).strftime('%H:%M')}"
            )
            cursor += slot_dur
            if len(free_slots) >= 10:
                return free_slots
        if be > cursor:
            cursor = be

    while cursor + slot_dur <= end_window:
        free_slots.append(
            f"{cursor.strftime('%Y-%m-%d %H:%M')} – {(cursor + slot_dur).strftime('%H:%M')}"
        )
        cursor += slot_dur
        if len(free_slots) >= 10:
            break

    return free_slots


class CalendarSkill(BaseSkill):
    """Manage calendar events via ICS files.

    Supported actions (via context.parameters["action"]):
        list    — Show upcoming events (default)
        create  — Create a new event (requires title, start; optional end, location, description)
        free    — Find free time slots in the next N days
    """

    metadata = SkillMetadata(
        name="calendar",
        version="1.0.0",
        description="Create, list, and find free slots in your calendar (ICS)",
        author="JARVIS Team",
        tags=["calendar", "schedule", "events"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        if not ICALENDAR_AVAILABLE:
            return SkillResult(
                success=False,
                error=(
                    "The 'icalendar' package is not installed. "
                    "Install it with: pip install icalendar"
                ),
            )

        action = context.parameters.get("action", "list").lower().strip()

        if action == "create":
            return await self._create_event(context)
        if action == "free":
            return await self._free_slots(context)
        return await self._list_events(context)

    # ── List upcoming events ────────────────────────────────────

    async def _list_events(self, context: SkillContext) -> SkillResult:
        path = _calendar_path(context)
        if not path.exists():
            return SkillResult(
                success=True,
                output="No calendar events found. Create one first.",
                metadata={"ics_path": str(path)},
            )

        try:
            cal = _load_calendar(path)
        except Exception as exc:
            return SkillResult(success=False, error=f"Failed to parse calendar: {exc}")

        limit = int(context.parameters.get("limit", 10))
        now = datetime.now(timezone.utc)

        upcoming: list[tuple[datetime, Event]] = []
        for comp in cal.walk("VEVENT"):
            dtstart = _parse_dt(comp.get("DTSTART"))
            if dtstart is None:
                continue
            if dtstart.tzinfo is None:
                dtstart = dtstart.replace(tzinfo=timezone.utc)
            if dtstart >= now:
                upcoming.append((dtstart, comp))

        upcoming.sort(key=lambda x: x[0])
        upcoming = upcoming[:limit]

        if not upcoming:
            return SkillResult(
                success=True,
                output="No upcoming events in your calendar.",
                metadata={"ics_path": str(path)},
            )

        lines = [_format_event(evt, i + 1) for i, (_, evt) in enumerate(upcoming)]
        header = f"Upcoming events ({len(upcoming)}):\n\n"

        return SkillResult(
            success=True,
            output=header + "\n\n".join(lines),
            metadata={"ics_path": str(path), "count": len(upcoming)},
        )

    # ── Create event ────────────────────────────────────────────

    async def _create_event(self, context: SkillContext) -> SkillResult:
        title = context.parameters.get("title", "").strip()
        start_str = context.parameters.get("start", "").strip()

        if not title:
            return SkillResult(success=False, error="Event title is required (parameter 'title').")
        if not start_str:
            return SkillResult(success=False, error="Event start time is required (parameter 'start').")

        try:
            start_dt = datetime.fromisoformat(start_str)
        except ValueError:
            return SkillResult(
                success=False,
                error=f"Invalid start datetime format: '{start_str}'. Use ISO format (e.g. 2025-03-15T14:00).",
            )

        end_str = context.parameters.get("end", "").strip()
        if end_str:
            try:
                end_dt = datetime.fromisoformat(end_str)
            except ValueError:
                return SkillResult(success=False, error=f"Invalid end datetime format: '{end_str}'.")
        else:
            end_dt = start_dt + timedelta(hours=1)

        location = context.parameters.get("location", "").strip()
        description = context.parameters.get("description", "").strip()

        event = Event()
        event.add("uid", str(uuid4()))
        event.add("summary", title)
        event.add("dtstart", start_dt)
        event.add("dtend", end_dt)
        event.add("dtstamp", datetime.now(timezone.utc))
        if location:
            event.add("location", location)
        if description:
            event.add("description", description)

        path = _calendar_path(context)
        try:
            cal = _load_calendar(path)
            cal.add_component(event)
            _save_calendar(cal, path)
        except Exception as exc:
            return SkillResult(success=False, error=f"Failed to save event: {exc}")

        start_fmt = start_dt.strftime("%Y-%m-%d %H:%M")
        end_fmt = end_dt.strftime("%H:%M")
        return SkillResult(
            success=True,
            output=f"Event '{title}' created: {start_fmt} – {end_fmt}",
            metadata={
                "uid": str(event.get("uid")),
                "title": title,
                "start": start_fmt,
                "end": end_fmt,
                "ics_path": str(path),
            },
        )

    # ── Find free slots ─────────────────────────────────────────

    async def _free_slots(self, context: SkillContext) -> SkillResult:
        path = _calendar_path(context)
        if not path.exists():
            return SkillResult(
                success=True,
                output="No calendar events found. The entire schedule is free.",
                metadata={"ics_path": str(path)},
            )

        try:
            cal = _load_calendar(path)
        except Exception as exc:
            return SkillResult(success=False, error=f"Failed to parse calendar: {exc}")

        days = int(context.parameters.get("days", 7))
        slot_min = int(context.parameters.get("slot_minutes", 60))

        free = _find_free_slots(cal, days_ahead=days, slot_minutes=slot_min)

        if not free:
            return SkillResult(
                success=True,
                output=f"No free {slot_min}-minute slots found in the next {days} days.",
                metadata={"days": days, "slot_minutes": slot_min},
            )

        header = f"Free {slot_min}-minute slots (next {days} days):\n\n"
        lines = [f"  {i+1}. {slot}" for i, slot in enumerate(free)]

        return SkillResult(
            success=True,
            output=header + "\n".join(lines),
            metadata={"days": days, "slot_minutes": slot_min, "count": len(free)},
        )
