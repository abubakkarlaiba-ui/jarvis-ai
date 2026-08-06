"""
Workflow Engine — structured logging.
=====================================
Provides WorkflowLogger for persisting workflow execution logs to disk.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from jarvis.core.workflow.base import LogEntry, Step, StepResult, Workflow


class WorkflowLogger:
    """Structured logger for workflow execution.

    Keeps a rolling in-memory buffer of the most recent 1000 entries and
    persists every entry to a daily log file under the configured directory.
    """

    MAX_MEMORY_ENTRIES = 1000

    def __init__(self, log_dir: str = "./data/workflows/logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[LogEntry] = []

    # ------------------------------------------------------------------
    # Core logging
    # ------------------------------------------------------------------

    def log(
        self,
        level: str,
        message: str,
        workflow_id: str = "",
        step_id: str = "",
        data: dict | None = None,
    ) -> None:
        """Create a LogEntry and store it."""
        entry = LogEntry(
            timestamp=datetime.now(),
            workflow_id=workflow_id,
            step_id=step_id,
            level=level.upper(),
            message=message,
            data=data or {},
        )
        self._write_log(entry)

    def info(
        self,
        message: str,
        workflow_id: str = "",
        step_id: str = "",
        data: dict | None = None,
    ) -> None:
        self.log("INFO", message, workflow_id, step_id, data)

    def warning(
        self,
        message: str,
        workflow_id: str = "",
        step_id: str = "",
        data: dict | None = None,
    ) -> None:
        self.log("WARNING", message, workflow_id, step_id, data)

    def error(
        self,
        message: str,
        workflow_id: str = "",
        step_id: str = "",
        data: dict | None = None,
    ) -> None:
        self.log("ERROR", message, workflow_id, step_id, data)

    def debug(
        self,
        message: str,
        workflow_id: str = "",
        step_id: str = "",
        data: dict | None = None,
    ) -> None:
        self.log("DEBUG", message, workflow_id, step_id, data)

    # ------------------------------------------------------------------
    # Convenience helpers for step / workflow lifecycle events
    # ------------------------------------------------------------------

    def step_started(self, step: Step, workflow_id: str) -> None:
        """Log the beginning of a step execution."""
        self.info(
            f"Step started: {step.name or step.id}",
            workflow_id=workflow_id,
            step_id=step.id,
            data={"step_type": step.step_type.value, "command": step.command},
        )

    def step_completed(
        self, step: Step, workflow_id: str, result: StepResult
    ) -> None:
        """Log a successful step completion."""
        self.info(
            f"Step completed: {step.name or step.id}",
            workflow_id=workflow_id,
            step_id=step.id,
            data={
                "duration": result.duration,
                "retries": result.retries,
                "output": result.output,
            },
        )

    def step_failed(
        self, step: Step, workflow_id: str, error: str
    ) -> None:
        """Log a step failure."""
        self.error(
            f"Step failed: {step.name or step.id} — {error}",
            workflow_id=workflow_id,
            step_id=step.id,
            data={"error": error},
        )

    def workflow_started(self, workflow: Workflow) -> None:
        """Log the start of a workflow."""
        self.info(
            f"Workflow started: {workflow.name or workflow.id}",
            workflow_id=workflow.id,
            data={
                "step_count": len(workflow.steps),
                "tags": workflow.tags,
            },
        )

    def workflow_completed(self, workflow: Workflow) -> None:
        """Log workflow completion."""
        self.info(
            f"Workflow completed: {workflow.name or workflow.id}",
            workflow_id=workflow.id,
            data={
                "step_count": len(workflow.steps),
                "results_count": len(workflow.results),
            },
        )

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_logs(
        self,
        workflow_id: str,
        level: str | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Retrieve logs for a workflow, optionally filtered by level."""
        filtered = [
            e
            for e in self._buffer
            if e.workflow_id == workflow_id
            and (level is None or e.level == level.upper())
        ]
        return filtered[-limit:]

    def get_step_logs(self, workflow_id: str, step_id: str) -> list[LogEntry]:
        """Return every log entry for a specific step within a workflow."""
        return [
            e
            for e in self._buffer
            if e.workflow_id == workflow_id and e.step_id == step_id
        ]

    def export_logs(
        self, workflow_id: str, format: str = "json"
    ) -> str:
        """Export filtered logs as a JSON string or human-readable text."""
        logs = [e for e in self._buffer if e.workflow_id == workflow_id]

        if format == "json":
            return json.dumps(
                [
                    {
                        "timestamp": e.timestamp.isoformat(),
                        "workflow_id": e.workflow_id,
                        "step_id": e.step_id,
                        "level": e.level,
                        "message": e.message,
                        "data": e.data,
                    }
                    for e in logs
                ],
                indent=2,
            )

        # plain text fallback
        lines = []
        for e in logs:
            ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            step = f" [step:{e.step_id}]" if e.step_id else ""
            lines.append(f"{ts} [{e.level}]{step} {e.message}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_log(self, entry: LogEntry) -> None:
        """Persist a log entry to disk and the in-memory buffer."""
        self._buffer.append(entry)
        if len(self._buffer) > self.MAX_MEMORY_ENTRIES:
            self._buffer = self._buffer[-self.MAX_MEMORY_ENTRIES :]

        log_file = self.log_dir / f"{entry.timestamp.strftime('%Y-%m-%d')}.log"
        record = {
            "timestamp": entry.timestamp.isoformat(),
            "workflow_id": entry.workflow_id,
            "step_id": entry.step_id,
            "level": entry.level,
            "message": entry.message,
            "data": entry.data,
        }
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
