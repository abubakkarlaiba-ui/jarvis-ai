"""
Workflow Engine — progress tracking and ETA estimation.
======================================================
Tracks step completion, estimates remaining time, and reports status.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from jarvis.core.workflow.base import (
    ProgressUpdate,
    Step,
    StepStatus,
    Workflow,
    WorkflowStatus,
)


class ProgressTracker:
    """Tracks workflow progress and estimates completion time.

    Maintains historical step durations to improve ETA estimates
    over repeated workflow executions.
    """

    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._step_starts: dict[str, dict[str, float]] = {}
        self._step_durations: dict[str, list[float]] = defaultdict(list)
        self._started_at: dict[str, float] = {}

    def start_workflow(self, workflow: Workflow) -> None:
        """Initialize tracking for a workflow."""
        self._workflows[workflow.id] = workflow
        self._step_starts[workflow.id] = {}
        self._started_at[workflow.id] = time.time()

    def update_step(
        self,
        step_id: str,
        status: StepStatus,
        output: Any = None,
    ) -> None:
        """Update a step's status and record timing."""
        wf = self._find_workflow_by_step(step_id)
        if wf is None:
            return

        now = time.time()

        if status in (StepStatus.RUNNING, StepStatus.RETRYING):
            self._step_starts[wf.id][step_id] = now
        elif status in (StepStatus.SUCCESS, StepStatus.FAILED, StepStatus.SKIPPED):
            start = self._step_starts.get(wf.id, {}).pop(step_id, None)
            if start is not None:
                duration = now - start
                step = self._get_step(wf, step_id)
                if step is not None:
                    self._step_durations[step.step_type.value].append(duration)

        for step in wf.steps:
            if step.id == step_id:
                step.status = status
                step.completed_at = None
                if status in (StepStatus.SUCCESS, StepStatus.FAILED):
                    from datetime import datetime
                    step.completed_at = datetime.now()
                if output is not None:
                    if step.result is None:
                        from jarvis.core.workflow.base import StepResult
                        step.result = StepResult(step_id=step_id, status=status, output=output)
                    else:
                        step.result.output = output
                        step.result.status = status
                break

    def get_progress(self, workflow_id: str) -> ProgressUpdate:
        """Get current progress snapshot for a workflow."""
        wf = self._workflows.get(workflow_id)
        if wf is None:
            return ProgressUpdate(workflow_id=workflow_id, message="Workflow not found")

        total = len(wf.steps)
        completed = sum(
            1 for s in wf.steps
            if s.status in (StepStatus.SUCCESS, StepStatus.SKIPPED)
        )
        failed = sum(
            1 for s in wf.steps if s.status == StepStatus.FAILED
        )

        current = ""
        for s in wf.steps:
            if s.status == StepStatus.RUNNING:
                current = s.name or s.id
                break

        elapsed = time.time() - self._started_at.get(wf.id, time.time())
        percent = self._calculate_percent(completed, total)
        eta = self.get_eta(workflow_id)

        return ProgressUpdate(
            workflow_id=wf.id,
            workflow_name=wf.name,
            status=wf.status,
            total_steps=total,
            completed_steps=completed,
            failed_steps=failed,
            current_step=current,
            percent=percent,
            eta_seconds=eta,
            elapsed_seconds=elapsed,
        )

    def get_eta(self, workflow_id: str) -> float:
        """Estimate remaining time in seconds."""
        wf = self._workflows.get(workflow_id)
        if wf is None:
            return 0.0

        remaining = [s for s in wf.steps if s.status in (StepStatus.PENDING, StepStatus.WAITING, StepStatus.READY)]
        completed = [s for s in wf.steps if s.status in (StepStatus.SUCCESS, StepStatus.SKIPPED)]
        return self._estimate_remaining(remaining, completed)

    def get_step_durations(self) -> dict[str, float]:
        """Return average durations per step type."""
        averages: dict[str, float] = {}
        for step_type, durations in self._step_durations.items():
            if durations:
                averages[step_type] = sum(durations) / len(durations)
        return averages

    def get_summary(self, workflow_id: str) -> str:
        """Return a human-readable progress summary."""
        prog = self.get_progress(workflow_id)
        lines = [
            f"Workflow: {prog.workflow_name or prog.workflow_id}",
            f"Status: {prog.status.name}",
            f"Progress: {prog.completed_steps}/{prog.total_steps} steps ({prog.percent:.1f}%)",
        ]
        if prog.current_step:
            lines.append(f"Current step: {prog.current_step}")
        if prog.failed_steps:
            lines.append(f"Failed: {prog.failed_steps} step(s)")
        if prog.eta_seconds > 0:
            lines.append(f"ETA: {prog.eta_seconds:.0f}s")
        if prog.elapsed_seconds > 0:
            lines.append(f"Elapsed: {prog.elapsed_seconds:.0f}s")
        return "\n".join(lines)

    def _calculate_percent(self, completed: int, total: int) -> float:
        """Calculate completion percentage."""
        if total <= 0:
            return 100.0
        return (completed / total) * 100.0

    def _estimate_remaining(
        self,
        steps: list[Step],
        completed: list[str],
    ) -> float:
        """Estimate remaining time based on historical averages."""
        if not steps:
            return 0.0

        total = 0.0
        for step in steps:
            avg = self._step_durations.get(step.step_type.value)
            if avg and avg > 0:
                total += avg[-1] if isinstance(avg, list) else avg
            else:
                total += step.timeout if step.timeout > 0 else 30.0

        return total

    def _find_workflow_by_step(self, step_id: str) -> Workflow | None:
        for wf in self._workflows.values():
            for s in wf.steps:
                if s.id == step_id:
                    return wf
        return None

    def _get_step(self, wf: Workflow, step_id: str) -> Step | None:
        for s in wf.steps:
            if s.id == step_id:
                return s
        return None
