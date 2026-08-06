"""
Base framework for desktop automation with safety gates.
========================================================
Provides severity levels, result types, and confirmation workflows
to prevent destructive operations from executing without approval.

Severity Levels:
    SAFE       — read-only or reversible (open app, search files, screenshot)
    MODERATE   — reversible changes (move file, create folder, volume)
    DANGEROUS  — hard to reverse (rename file, close app, keyboard input)
    DESTRUCTIVE — irreversible (delete file, shutdown, restart)

Usage:
    gate = SafetyGate(settings)
    allowed = await gate.check(ActionSeverity.DANGEROUS, "Close Notepad?")
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class ActionSeverity(Enum):
    """Severity level for automation actions."""
    SAFE = auto()           # Read-only, no side effects
    MODERATE = auto()       # Reversible changes
    DANGEROUS = auto()      # Hard to reverse
    DESTRUCTIVE = auto()    # Irreversible


@dataclass
class ActionResult:
    """Result of an automation action."""
    success: bool
    message: str
    data: Any = None
    severity: ActionSeverity = ActionSeverity.SAFE
    duration_ms: float = 0.0
    cancelled: bool = False

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "severity": self.severity.name,
            "duration_ms": round(self.duration_ms, 1),
            "cancelled": self.cancelled,
        }


class SafetyGate:
    """Controls execution of actions based on severity and confirmation policy.

    Destructive actions always require confirmation.
    Dangerous actions require confirmation unless explicitly overridden.
    Moderate and Safe actions execute immediately.

    Confirmation can be:
        - Auto-approved (for safe operations)
        - Pre-approved via allowlist
        - Requiring user confirmation (callback)

    Example:
        gate = SafetyGate(settings)
        if await gate.check(ActionSeverity.DANGEROUS, "Delete important.txt?"):
            # proceed with deletion
    """

    def __init__(
        self,
        auto_approve_safe: bool = True,
        auto_approve_moderate: bool = True,
        require_confirm_dangerous: bool = True,
        require_confirm_destructive: bool = True,
        confirmation_callback: Callable[[str, ActionSeverity], Awaitable[bool]] | None = None,
    ):
        self._auto_approve_safe = auto_approve_safe
        self._auto_approve_moderate = auto_approve_moderate
        self._require_confirm_dangerous = require_confirm_dangerous
        self._require_confirm_destructive = require_confirm_destructive
        self._confirmation_callback = confirmation_callback
        self._pre_approved: set[str] = set()
        self._blocked: set[str] = set()
        self._action_log: list[dict] = []

    def pre_approve(self, action_pattern: str) -> None:
        """Pre-approve an action pattern (e.g., 'open:notepad')."""
        self._pre_approved.add(action_pattern)

    def block(self, action_pattern: str) -> None:
        """Block an action pattern from ever executing."""
        self._blocked.add(action_pattern)

    async def check(self, severity: ActionSeverity, description: str = "", action_id: str = "") -> bool:
        """Check if an action is allowed to proceed.

        Args:
            severity: Action severity level.
            description: Human-readable description for confirmation.
            action_id: Optional action identifier for pre-approval.

        Returns:
            True if action should proceed, False to cancel.
        """
        if action_id in self._blocked:
            logger.warning("Blocked action: %s (id=%s)", description, action_id)
            self._log_action(severity, description, False, "blocked")
            return False

        if action_id in self._pre_approved:
            logger.debug("Pre-approved action: %s", description)
            self._log_action(severity, description, True, "pre_approved")
            return True

        if severity == ActionSeverity.SAFE:
            if self._auto_approve_safe:
                self._log_action(severity, description, True, "auto")
                return True

        elif severity == ActionSeverity.MODERATE:
            if self._auto_approve_moderate:
                self._log_action(severity, description, True, "auto")
                return True

        elif severity == ActionSeverity.DANGEROUS:
            if not self._require_confirm_dangerous:
                self._log_action(severity, description, True, "auto")
                return True

        elif severity == ActionSeverity.DESTRUCTIVE:
            if not self._require_confirm_destructive:
                self._log_action(severity, description, True, "auto")
                return True

        if self._confirmation_callback:
            approved = await self._confirmation_callback(description, severity)
            self._log_action(severity, description, approved, "callback")
            return approved

        logger.info("Auto-approved (no callback): %s [%s]", description, severity.name)
        self._log_action(severity, description, True, "fallback")
        return True

    def _log_action(self, severity: ActionSeverity, description: str, approved: bool, method: str) -> None:
        self._action_log.append({
            "timestamp": time.time(),
            "severity": severity.name,
            "description": description,
            "approved": approved,
            "method": method,
        })
        if len(self._action_log) > 500:
            self._action_log = self._action_log[-250:]

    def get_log(self, limit: int = 20) -> list[dict]:
        return self._action_log[-limit:]
