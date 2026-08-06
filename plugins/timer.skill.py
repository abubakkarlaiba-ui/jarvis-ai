"""
Skill: Timer
============
Countdown timers, alarms, and multi-timer management.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

logger = logging.getLogger(__name__)


@dataclass
class TimerEntry:
    id: str
    label: str
    duration_sec: float
    remaining_sec: float
    created_at: str
    expires_at: str
    task: asyncio.Task | None = None
    cancelled: bool = False


class TimerSkill(BaseSkill):
    metadata = SkillMetadata(
        name="timer",
        version="1.0.0",
        description="Start countdown timers, set alarms, and manage multiple timers",
        author="JARVIS Team",
        tags=["timer", "countdown", "reminder"],
    )

    def __init__(self) -> None:
        super().__init__()
        self._timers: dict[str, TimerEntry] = {}
        self._counter: int = 0

    async def on_shutdown(self) -> None:
        for entry in self._timers.values():
            if entry.task and not entry.task.done():
                entry.cancelled = True
                entry.task.cancel()
        self._timers.clear()

    async def execute(self, context: SkillContext) -> SkillResult:
        action = context.parameters.get("action", "").lower()
        if not action:
            action = context.user_input.strip().split()[0] if context.user_input.strip() else ""

        handlers: dict[str, Any] = {
            "start": self._start,
            "set": self._start,
            "list": self._list,
            "active": self._list,
            "cancel": self._cancel,
            "stop": self._cancel,
        }

        handler = handlers.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {', '.join(handlers)}",
            )
        return await handler(context)

    async def _start(self, context: SkillContext) -> SkillResult:
        duration = context.parameters.get("duration")
        label = context.parameters.get("label", "")

        if duration is None:
            raw = context.user_input.strip()
            parts = raw.split(maxsplit=1)
            if len(parts) >= 2:
                label = parts[1]
            duration = self._parse_duration(parts[0]) if parts else None

        if duration is None or duration <= 0:
            return SkillResult(success=False, error="Provide a positive duration (e.g. '30s', '5m', '1h30m').")

        if isinstance(duration, (int, float)) and duration > 0:
            pass
        else:
            return SkillResult(success=False, error="Invalid duration format.")

        self._counter += 1
        timer_id = f"t{self._counter}"
        now = datetime.now(timezone.utc)
        expires = datetime.fromtimestamp(now.timestamp() + duration, tz=timezone.utc)

        entry = TimerEntry(
            id=timer_id,
            label=label or f"Timer {timer_id}",
            duration_sec=duration,
            remaining_sec=duration,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )

        entry.task = asyncio.create_task(self._run_timer(entry))
        self._timers[timer_id] = entry

        return SkillResult(
            success=True,
            output=f"Timer '{entry.label}' started for {self._fmt_duration(duration)} (id: {timer_id}).",
            metadata={"timer_id": timer_id, "label": entry.label, "duration_sec": duration},
        )

    async def _list(self, context: SkillContext) -> SkillResult:
        active = [e for e in self._timers.values() if not e.cancelled]
        if not active:
            return SkillResult(success=True, output="No active timers.")

        lines = [f"[{e.id}] {e.label} — {self._fmt_duration(e.remaining_sec)} remaining" for e in active]
        return SkillResult(success=True, output="\n".join(lines), metadata={"count": len(active)})

    async def _cancel(self, context: SkillContext) -> SkillResult:
        timer_id = context.parameters.get("id", "").strip()
        if not timer_id:
            return SkillResult(success=False, error="A timer id is required.")

        entry = self._timers.get(timer_id)
        if not entry or entry.cancelled:
            return SkillResult(success=False, error=f"Timer '{timer_id}' not found or already cancelled.")

        entry.cancelled = True
        if entry.task and not entry.task.done():
            entry.task.cancel()
        self._timers.pop(timer_id, None)

        return SkillResult(success=True, output=f"Timer '{entry.label}' ({timer_id}) cancelled.")

    async def _run_timer(self, entry: TimerEntry) -> None:
        try:
            await asyncio.sleep(entry.duration_sec)
        except asyncio.CancelledError:
            return

        if not entry.cancelled:
            self._timers.pop(entry.id, None)
            logger.info("Timer expired: [%s] %s", entry.id, entry.label)
            print(f"Timer '{entry.label}' ({entry.id}) has expired!")

    @staticmethod
    def _parse_duration(raw: str) -> float | None:
        raw = raw.strip().lower()
        if not raw:
            return None

        total = 0.0
        current = ""

        for ch in raw:
            if ch.isdigit() or ch == ".":
                current += ch
            elif ch in ("h", "m", "s"):
                if not current:
                    return None
                val = float(current)
                if ch == "h":
                    total += val * 3600
                elif ch == "m":
                    total += val * 60
                elif ch == "s":
                    total += val
                current = ""
            else:
                return None

        if current:
            total += float(current)

        return total if total > 0 else None

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h{m:02d}m{s:02d}s"
        if m:
            return f"{m}m{s:02d}s"
        return f"{s}s"
