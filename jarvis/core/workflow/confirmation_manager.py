"""
Workflow Engine — confirmation prompt management.
================================================
Manages confirmation requests for risky workflow steps.
"""

from __future__ import annotations

import uuid
from typing import Any

from jarvis.core.workflow.base import Step, StepRisk


class ConfirmationManager:
    """Manages confirmation prompts for risky workflow steps.

    Stores pending confirmations keyed by confirmation_id and
    uses risk levels to determine which steps require approval.
    """

    def __init__(self) -> None:
        self._pending: dict[str, dict[str, Any]] = {}

    def needs_confirmation(self, step: Step) -> bool:
        """Check if a step requires confirmation based on risk level."""
        return step.risk in (StepRisk.MEDIUM, StepRisk.HIGH, StepRisk.DESTRUCTIVE)

    def request_confirmation(self, step: Step, reason: str) -> str:
        """Create a confirmation request and return the confirmation_id."""
        confirmation_id = uuid.uuid4().hex
        self._pending[confirmation_id] = {
            "confirmation_id": confirmation_id,
            "step_id": step.id,
            "step_name": step.name,
            "risk": step.risk,
            "reason": reason,
            "approved": None,
            "message": "",
        }
        return confirmation_id

    def confirm(
        self,
        confirmation_id: str,
        approved: bool,
        message: str = "",
    ) -> bool:
        """Respond to a confirmation. Returns True if response was accepted."""
        entry = self._pending.get(confirmation_id)
        if entry is None:
            return False
        entry["approved"] = approved
        entry["message"] = message
        self._pending.pop(confirmation_id, None)
        return True

    def is_pending(self, confirmation_id: str) -> bool:
        """Check if a confirmation is still pending."""
        return confirmation_id in self._pending

    def get_pending(self) -> list[dict]:
        """List all pending confirmations."""
        return list(self._pending.values())

    def cancel(self, confirmation_id: str) -> None:
        """Cancel a pending confirmation."""
        self._pending.pop(confirmation_id, None)

    def auto_approve_low_risk(self, steps: list[Step]) -> list[Step]:
        """Filter out low-risk steps that don't need confirmation.

        Returns only the steps that still require user confirmation.
        """
        return [s for s in steps if s.risk != StepRisk.LOW]

    def format_prompt(self, step: Step, reason: str) -> str:
        """Format a human-readable confirmation prompt."""
        risk_label = step.risk.name
        return (
            f"[{risk_label}] Confirmation required\n"
            f"Step: {step.name or step.id}\n"
            f"Type: {step.step_type.value}\n"
            f"Reason: {reason}\n"
            f"Command: {step.command[:80] if step.command else '(none)'}"
        )
