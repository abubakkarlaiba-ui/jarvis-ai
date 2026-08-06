"""
Security module — confirmation prompts for sensitive actions.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jarvis.core.security.base import AuditAction, BackupManifest, User

_HISTORY_PATH = Path("./data/security/confirmation_history.jsonl")

_RISK_LEVELS = {"low", "medium", "high", "destructive"}

_DESTRUCTIVE_ACTIONS = {
    "system.shutdown",
    "file.delete",
    "workflow.delete",
    "skill.remove",
    "backup.delete",
    "database.drop",
    "config.reset",
}


class ConfirmationManager:
    def __init__(self, timeout: int = 300, data_dir: str = "./data/security") -> None:
        self.timeout = timeout
        self.data_dir = Path(data_dir)
        self._pending: dict[str, dict[str, Any]] = {}
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ── core API ─────────────────────────────────────────────────
    def request_confirmation(
        self,
        action: str,
        resource: str,
        user_id: str,
        details: dict | None = None,
        risk_level: str = "medium",
    ) -> dict[str, Any]:
        if risk_level not in _RISK_LEVELS:
            raise ValueError(f"Invalid risk level: {risk_level}. Must be one of {_RISK_LEVELS}")

        if self._auto_approve_check(action, user_id):
            return {
                "id": "auto-approved",
                "action": action,
                "resource": resource,
                "risk_level": risk_level,
                "expires_at": datetime.now().isoformat(),
                "prompt": "Auto-approved",
                "auto_approved": True,
            }

        if self.requires_two_factor(action) and risk_level not in ("high", "destructive"):
            risk_level = "high"

        now = datetime.now()
        confirmation_id = uuid.uuid4().hex[:12]
        expires_at = now + timedelta(seconds=self.timeout)

        prompt = self._generate_prompt(action, resource, risk_level, details)

        confirmation = {
            "id": confirmation_id,
            "action": action,
            "resource": resource,
            "user_id": user_id,
            "risk_level": risk_level,
            "details": details or {},
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "prompt": prompt,
            "status": "pending",
            "approved": None,
            "reason": "",
        }

        self._pending[confirmation_id] = confirmation
        self._append_history(confirmation)
        return confirmation

    def confirm(
        self, confirmation_id: str, approved: bool, user_id: str, reason: str = ""
    ) -> bool:
        confirmation = self._pending.get(confirmation_id)
        if not confirmation:
            return False

        if confirmation["status"] != "pending":
            return False

        if datetime.fromisoformat(confirmation["expires_at"]) <= datetime.now():
            confirmation["status"] = "expired"
            self._append_history(confirmation)
            del self._pending[confirmation_id]
            return False

        if confirmation["risk_level"] == "destructive" and not reason.strip():
            return False

        confirmation["status"] = "approved" if approved else "denied"
        confirmation["approved"] = approved
        confirmation["reason"] = reason
        confirmation["responded_at"] = datetime.now().isoformat()
        confirmation["responded_by"] = user_id

        self._append_history(confirmation)
        del self._pending[confirmation_id]
        return True

    def is_pending(self, confirmation_id: str) -> bool:
        confirmation = self._pending.get(confirmation_id)
        if not confirmation:
            return False
        if self.is_expired(confirmation_id):
            del self._pending[confirmation_id]
            return False
        return confirmation["status"] == "pending"

    def is_expired(self, confirmation_id: str) -> bool:
        confirmation = self._pending.get(confirmation_id)
        if not confirmation:
            return True
        return datetime.fromisoformat(confirmation["expires_at"]) <= datetime.now()

    def get_pending(self, user_id: str | None = None) -> list[dict[str, Any]]:
        self.cleanup_expired()
        results = []
        for c in self._pending.values():
            if c["status"] != "pending":
                continue
            if user_id and c["user_id"] != user_id:
                continue
            results.append(c)
        return results

    def cancel(self, confirmation_id: str) -> bool:
        confirmation = self._pending.get(confirmation_id)
        if not confirmation or confirmation["status"] != "pending":
            return False
        confirmation["status"] = "cancelled"
        self._append_history(confirmation)
        del self._pending[confirmation_id]
        return True

    def cleanup_expired(self) -> int:
        now = datetime.now()
        expired_ids = [
            cid
            for cid, c in self._pending.items()
            if c["status"] == "pending" and datetime.fromisoformat(c["expires_at"]) <= now
        ]
        for cid in expired_ids:
            confirmation = self._pending.pop(cid)
            confirmation["status"] = "expired"
            self._append_history(confirmation)
        return len(expired_ids)

    def get_history(self, count: int = 50) -> list[dict[str, Any]]:
        if not _HISTORY_PATH.exists():
            return []
        lines = _HISTORY_PATH.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines[-count:]:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return list(reversed(entries))

    # ── prompts ──────────────────────────────────────────────────
    def _generate_prompt(
        self,
        action: str,
        resource: str,
        risk_level: str,
        details: dict | None,
    ) -> str:
        badge = self.format_risk_badge(risk_level)
        detail_text = ""
        if details:
            detail_items = [f"  {k}: {v}" for k, v in details.items()]
            detail_text = "\n" + "\n".join(detail_items)

        requires_2fa = self.requires_two_factor(action)
        tfa_note = "\nTwo-factor authentication required." if requires_2fa else ""

        return (
            f"{badge}\n"
            f"Action: {action}\n"
            f"Resource: {resource}\n"
            f"Risk: {risk_level.upper()}{tfa_note}"
            f"{detail_text}\n"
            f"Do you approve this action?"
        )

    # ── risk helpers ─────────────────────────────────────────────
    def _auto_approve_check(self, action: str, user_id: str) -> bool:
        risk = self._get_action_risk(action)
        return risk == "low"

    def _get_action_risk(self, action: str) -> str:
        if action in _DESTRUCTIVE_ACTIONS:
            return "destructive"
        return "medium"

    def format_risk_badge(self, risk_level: str) -> str:
        colors = {
            "low": "#22c55e",
            "medium": "#f59e0b",
            "high": "#ef4444",
            "destructive": "#7c3aed",
        }
        color = colors.get(risk_level, "#6b7280")
        return (
            f'<span style="background:{color};color:white;'
            f'padding:2px 8px;border-radius:4px;font-weight:bold;">'
            f"{risk_level.upper()}</span>"
        )

    def requires_two_factor(self, action: str) -> bool:
        return action in _DESTRUCTIVE_ACTIONS

    # ── persistence ──────────────────────────────────────────────
    def _append_history(self, confirmation: dict[str, Any]) -> None:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(confirmation, default=str) + "\n")
