"""
Workflow Engine — retry handler.
================================
Handles retries with exponential backoff and circuit breaker pattern.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from jarvis.core.workflow.base import Step

CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_RESET_SECONDS = 30.0


@dataclass
class _FailureRecord:
    """Tracks a single failure for a step."""
    timestamp: float
    error: str


class RetryHandler:
    """Handle retries with exponential backoff and circuit breaker."""

    def __init__(self) -> None:
        self._failures: dict[str, list[_FailureRecord]] = {}
        self._circuit_open_at: dict[str, float | None] = {}

    def should_retry(self, step: Step, error: Exception) -> bool:
        """Check if step should retry based on its policy."""
        if step.max_retries <= 0:
            return False

        if self.is_circuit_open(step.id):
            return False

        retries = step.result.retries if step.result else 0
        if retries >= step.max_retries:
            return False

        return True

    def get_delay(self, step: Step, attempt: int) -> float:
        """Calculate delay for attempt using exponential backoff.

        delay = retry_delay * (retry_backoff ^ attempt)
        """
        delay = step.retry_delay * (step.retry_backoff ** attempt)
        return delay

    def record_failure(self, step_id: str) -> None:
        """Record a failure for circuit breaker tracking."""
        if step_id not in self._failures:
            self._failures[step_id] = []

        self._failures[step_id].append(
            _FailureRecord(timestamp=time.time(), error="")
        )

        recent = [
            f for f in self._failures[step_id]
            if time.time() - f.timestamp < CIRCUIT_BREAKER_RESET_SECONDS
        ]
        self._failures[step_id] = recent

        if len(recent) >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open_at[step_id] = time.time()

    def record_success(self, step_id: str) -> None:
        """Record success — reset circuit breaker and failure count."""
        self._failures.pop(step_id, None)
        self._circuit_open_at.pop(step_id, None)

    def is_circuit_open(self, step_id: str) -> bool:
        """Check if circuit breaker is open (too many failures).

        Opens after CIRCUIT_BREAKER_THRESHOLD consecutive failures.
        Resets automatically after CIRCUIT_BREAKER_RESET_SECONDS.
        """
        open_at = self._circuit_open_at.get(step_id)
        if open_at is None:
            return False

        elapsed = time.time() - open_at
        if elapsed >= CIRCUIT_BREAKER_RESET_SECONDS:
            self._circuit_open_at.pop(step_id, None)
            return False

        return True

    def get_retry_info(self, step: Step) -> dict[str, Any]:
        """Return retry status info for a step."""
        retries = step.result.retries if step.result else 0
        failures = self._failures.get(step.id, [])
        circuit_open = self.is_circuit_open(step.id)

        return {
            "step_id": step.id,
            "retries_used": retries,
            "max_retries": step.max_retries,
            "retries_remaining": max(0, step.max_retries - retries),
            "circuit_open": circuit_open,
            "recent_failures": len(failures),
            "next_delay": self.get_delay(step, retries),
        }

    def reset(self, step_id: str) -> None:
        """Reset retry state for a step."""
        self._failures.pop(step_id, None)
        self._circuit_open_at.pop(step_id, None)
