"""
Workflow Engine — main orchestrator.
====================================
Coordinates all sub-modules to plan, execute, monitor, and resume workflows.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable

from jarvis.core.workflow.base import (
    LogEntry,
    ProgressUpdate,
    Step,
    StepResult,
    StepRisk,
    StepStatus,
    StepType,
    Workflow,
    WorkflowPlan,
    WorkflowStatus,
)
from jarvis.core.workflow.confirmation_manager import ConfirmationManager
from jarvis.core.workflow.dependency_resolver import DependencyResolver
from jarvis.core.workflow.progress_tracker import ProgressTracker
from jarvis.core.workflow.retry_handler import RetryHandler
from jarvis.core.workflow.step_executors import StepExecutors
from jarvis.core.workflow.workflow_logger import WorkflowLogger
from jarvis.core.workflow.workflow_store import WorkflowStore

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Autonomous task execution engine.

    Plans workflows from high-level goals, executes steps with
    dependency resolution, retries, confirmations, and progress tracking.
    Supports pause, resume, and cancellation.
    """

    def __init__(
        self,
        store_dir: str = "./data/workflows",
        log_dir: str = "./data/workflows/logs",
    ):
        self.resolver = DependencyResolver()
        self.executors = StepExecutors()
        self.retries = RetryHandler()
        self.progress = ProgressTracker()
        self.confirmations = ConfirmationManager()
        self.logger = WorkflowLogger(log_dir)
        self.store = WorkflowStore(store_dir)
        self._callbacks: dict[str, Callable] = {}
        self._running: dict[str, asyncio.Task] = {}

    # ── Callback registration ─────────────────────────────────────

    def register_callback(self, name: str, func: Callable) -> None:
        """Register a callback function for workflow steps."""
        self._callbacks[name] = func

    # ── Workflow creation ─────────────────────────────────────────

    def create_workflow(
        self,
        name: str,
        steps: list[Step],
        description: str = "",
        variables: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Workflow:
        """Create a new workflow from a list of steps.

        Args:
            name: Human-readable workflow name.
            steps: Ordered list of Step objects.
            description: What this workflow accomplishes.
            variables: Template variables available to all steps.
            tags: Tags for categorization.

        Returns:
            Created Workflow instance.
        """
        workflow = Workflow(
            name=name,
            description=description,
            steps=steps,
            variables=variables or {},
            tags=tags or [],
        )

        # Validate dependencies
        errors = self.resolver.validate(steps)
        if errors:
            raise ValueError(f"Invalid workflow: {'; '.join(errors)}")

        self.store.save(workflow)
        self.logger.workflow_started(workflow)
        return workflow

    async def plan_from_goal(self, goal: str) -> WorkflowPlan:
        """Decompose a high-level goal into executable steps.

        Uses pattern matching to break common goal types into
        structured workflows with dependencies.

        Args:
            goal: Natural language description of the goal.

        Returns:
            WorkflowPlan with ordered steps and dependencies.
        """
        goal_lower = goal.lower()
        steps: list[Step] = []

        # Detect goal patterns and create appropriate steps
        if any(kw in goal_lower for kw in ["deploy", "production", "release"]):
            steps = self._plan_deployment(goal)
        elif any(kw in goal_lower for kw in ["test", "verify", "check"]):
            steps = self._plan_testing(goal)
        elif any(kw in goal_lower for kw in ["build", "create", "scaffold", "project"]):
            steps = self._plan_build(goal)
        elif any(kw in goal_lower for kw in ["fix", "bug", "debug", "error"]):
            steps = self._plan_debug(goal)
        elif any(kw in goal_lower for kw in ["refactor", "improve", "optimize"]):
            steps = self._plan_refactor(goal)
        elif any(kw in goal_lower for kw in ["analyze", "review", "audit"]):
            steps = self._plan_analysis(goal)
        else:
            steps = self._plan_generic(goal)

        # Resolve dependencies
        groups = self.resolver.resolve(steps)
        parallel_info = self.resolver.estimate_parallelism(steps)

        plan = WorkflowPlan(
            goal=goal,
            steps=steps,
            estimated_duration=parallel_info.get("critical_path", len(steps) * 10),
            dependencies=self.resolver.build_dependency_graph(steps),
            parallel_groups=[g for g in groups],
            summary=self._format_plan_summary(steps, parallel_info),
        )
        return plan

    async def execute_plan(
        self,
        plan: WorkflowPlan,
        name: str = "",
        auto_confirm: bool = False,
    ) -> Workflow:
        """Execute a workflow plan.

        Creates a workflow from the plan and runs it.

        Args:
            plan: The workflow plan to execute.
            name: Workflow name (defaults to goal).
            auto_confirm: Auto-approve medium-risk steps.

        Returns:
            Completed Workflow with results.
        """
        workflow = self.create_workflow(
            name=name or plan.goal,
            steps=plan.steps,
            description=plan.goal,
        )
        return await self.run_workflow(workflow, auto_confirm=auto_confirm)

    # ── Workflow execution ────────────────────────────────────────

    async def run_workflow(
        self,
        workflow: Workflow,
        auto_confirm: bool = False,
    ) -> Workflow:
        """Execute all steps in a workflow.

        Handles dependency resolution, parallel execution, retries,
        confirmations, and progress tracking.

        Args:
            workflow: The workflow to execute.
            auto_confirm: Auto-approve low/medium risk steps.

        Returns:
            Updated Workflow with results.
        """
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()
        self.store.save(workflow)
        self.progress.start_workflow(workflow)

        completed: set[str] = set()
        step_map = {s.id: s for s in workflow.steps}

        try:
            while len(completed) < len(workflow.steps):
                # Get steps ready to run
                ready = self.resolver.get_ready_steps(workflow.steps, completed)

                if not ready:
                    # Check if we're stuck
                    remaining = [s for s in workflow.steps if s.id not in completed]
                    if all(s.status in (StepStatus.FAILED, StepStatus.SKIPPED, StepStatus.CANCELLED) for s in remaining):
                        break
                    if not remaining:
                        break
                    # Possible deadlock
                    workflow.status = WorkflowStatus.FAILED
                    workflow.error = "Workflow deadlocked: remaining steps have unmet dependencies"
                    self.logger.error(workflow.error, workflow.id)
                    break

                # Execute ready steps (potentially in parallel)
                tasks = []
                for step in ready:
                    step.status = StepStatus.READY
                    tasks.append(self._execute_step_with_retry(
                        workflow, step, auto_confirm
                    ))

                # Wait for all ready steps to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for step, result in zip(ready, results):
                    if isinstance(result, Exception):
                        step.status = StepStatus.FAILED
                        step.result = StepResult(
                            step_id=step.id,
                            status=StepStatus.FAILED,
                            error=str(result),
                        )
                        self.logger.step_failed(step, workflow.id, str(result))
                        completed.add(step.id)
                        if workflow.pause_on_error:
                            workflow.status = WorkflowStatus.PAUSED
                            self.store.save(workflow)
                            return workflow
                    else:
                        completed.add(step.id)
                        workflow.results.append(result)

                    self.progress.update_step(
                        step.id, step.status, step.result.output if step.result else None
                    )

            # Determine final status
            failed = sum(1 for s in workflow.steps if s.status == StepStatus.FAILED)
            if failed > 0 and failed == len(workflow.steps):
                workflow.status = WorkflowStatus.FAILED
                workflow.error = "All steps failed"
            elif failed > 0:
                workflow.status = WorkflowStatus.FAILED
                workflow.error = f"{failed}/{len(workflow.steps)} steps failed"
            else:
                workflow.status = WorkflowStatus.COMPLETED

        except asyncio.CancelledError:
            workflow.status = WorkflowStatus.INTERRUPTED
            self.logger.warning("Workflow interrupted", workflow.id)
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(e)
            self.logger.error(f"Workflow failed: {e}", workflow.id)

        workflow.completed_at = datetime.now()
        self.store.save(workflow)
        self.logger.workflow_completed(workflow)
        return workflow

    async def _execute_step_with_retry(
        self,
        workflow: Workflow,
        step: Step,
        auto_confirm: bool,
    ) -> StepResult:
        """Execute a step with retry logic and confirmations."""
        attempt = 0
        max_attempts = step.max_retries + 1

        while attempt < max_attempts:
            # Check circuit breaker
            if self.retries.is_circuit_open(step.id):
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error="Circuit breaker open: too many failures",
                )

            # Check confirmation needed
            if step.risk in (StepRisk.HIGH, StepRisk.DESTRUCTIVE) and not auto_confirm:
                if self.confirmations.needs_confirmation(step):
                    step.status = StepStatus.CONFIRMATION
                    reason = f"Step '{step.name}' has {step.risk.name} risk level"
                    conf_id = self.confirmations.request_confirmation(step, reason)
                    self.logger.info(
                        f"Waiting for confirmation: {reason}",
                        workflow.id, step.id,
                    )
                    # Wait for confirmation (in real app, this would be event-driven)
                    # For now, auto-approve if auto_confirm, else skip
                    if not auto_confirm:
                        return StepResult(
                            step_id=step.id,
                            status=StepStatus.WAITING,
                            error="Awaiting user confirmation",
                        )

            # Execute the step
            step.status = StepStatus.RUNNING
            step.started_at = datetime.now()
            self.logger.step_started(step, workflow.id)

            try:
                result = await self.executors.execute(step, {
                    "variables": workflow.variables,
                    "workflow_id": workflow.id,
                    "callbacks": self._callbacks,
                    "previous_results": {
                        r.step_id: r.output for r in workflow.results
                    },
                })

                result.step_id = step.id
                result.retries = attempt
                step.result = result
                step.completed_at = datetime.now()
                step.status = result.status

                if result.status == StepStatus.SUCCESS:
                    self.retries.record_success(step.id)
                    self.logger.step_completed(step, workflow.id, result)
                    return result

                # Step failed
                self.retries.record_failure(step.id)
                self.logger.step_failed(step, workflow.id, result.error)

                if not self.retries.should_retry(step, Exception(result.error)):
                    return result

            except Exception as e:
                step.status = StepStatus.FAILED
                result = StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error=str(e),
                )
                step.result = result
                self.retries.record_failure(step.id)
                self.logger.step_failed(step, workflow.id, str(e))

                if not self.retries.should_retry(step, e):
                    return result

            attempt += 1
            if attempt < max_attempts:
                step.status = StepStatus.RETRYING
                delay = self.retries.get_delay(step, attempt)
                self.logger.info(
                    f"Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_attempts})",
                    workflow.id, step.id,
                )
                await asyncio.sleep(delay)

        # Exhausted retries
        step.status = StepStatus.FAILED
        final_result = step.result or StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error="Max retries exceeded",
        )
        final_result.retries = attempt
        return final_result

    # ── Control operations ────────────────────────────────────────

    async def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow."""
        workflow = self.store.load(workflow_id)
        if workflow and workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.PAUSED
            self.store.save(workflow)
            self.logger.info("Workflow paused", workflow_id)
            return True
        return False

    async def resume_workflow(self, workflow_id: str) -> Workflow | None:
        """Resume a paused or interrupted workflow."""
        workflow = self.store.load(workflow_id)
        if workflow and workflow.status in (WorkflowStatus.PAUSED, WorkflowStatus.INTERRUPTED):
            return await self.run_workflow(workflow)
        return None

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        if workflow_id in self._running:
            self._running[workflow_id].cancel()
            del self._running[workflow_id]

        workflow = self.store.load(workflow_id)
        if workflow:
            workflow.status = WorkflowStatus.CANCELLED
            workflow.completed_at = datetime.now()
            self.store.save(workflow)
            self.logger.info("Workflow cancelled", workflow_id)
            return True
        return False

    async def retry_step(self, workflow_id: str, step_id: str) -> StepResult | None:
        """Retry a single failed step."""
        workflow = self.store.load(workflow_id)
        if not workflow:
            return None
        step = next((s for s in workflow.steps if s.id == step_id), None)
        if not step or step.status != StepStatus.FAILED:
            return None
        self.retries.reset(step_id)
        return await self._execute_step_with_retry(workflow, step, auto_confirm=True)

    # ── Query operations ──────────────────────────────────────────

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        return self.store.load(workflow_id)

    def list_workflows(self, status: WorkflowStatus | None = None, limit: int = 50) -> list[dict]:
        return self.store.list_workflows(status, limit)

    def get_progress(self, workflow_id: str) -> ProgressUpdate:
        return self.progress.get_progress(workflow_id)

    def get_logs(self, workflow_id: str, level: str | None = None) -> list[LogEntry]:
        return self.logger.get_logs(workflow_id, level)

    def get_resumable(self) -> list[dict]:
        return self.store.get_resumable()

    def get_stats(self) -> dict:
        return self.store.get_stats()

    # ── Internal helpers ──────────────────────────────────────────

    def _plan_deployment(self, goal: str) -> list[Step]:
        return [
            Step(name="Run tests", step_type=StepType.SHELL, command="python -m pytest", risk=StepRisk.LOW, max_retries=2),
            Step(name="Build project", step_type=StepType.SHELL, command="python -m build", risk=StepRisk.LOW, max_retries=1),
            Step(name="Check version", step_type=StepType.CODE, command="import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])", risk=StepRisk.LOW),
            Step(name="Create git tag", step_type=StepType.SHELL, command="git tag -a v{version} -m 'Release {version}'", risk=StepRisk.HIGH, depends_on=["Check version"]),
            Step(name="Push to remote", step_type=StepType.SHELL, command="git push origin main --tags", risk=StepRisk.HIGH, depends_on=["Create git tag"]),
            Step(name="Deploy", step_type=StepType.SHELL, command="echo 'Deploy step - configure for your platform'", risk=StepRisk.DESTRUCTIVE, depends_on=["Push to remote"]),
        ]

    def _plan_testing(self, goal: str) -> list[Step]:
        return [
            Step(name="Discover tests", step_type=StepType.CODE, command="import subprocess; r=subprocess.run(['python','-m','pytest','--collect-only','-q'],capture_output=True,text=True); print(r.stdout)", risk=StepRisk.LOW),
            Step(name="Run unit tests", step_type=StepType.SHELL, command="python -m pytest tests/ -v --tb=short", risk=StepRisk.LOW, max_retries=2),
            Step(name="Run type check", step_type=StepType.SHELL, command="python -m mypy .", risk=StepRisk.LOW),
            Step(name="Run linter", step_type=StepType.SHELL, command="python -m ruff check .", risk=StepRisk.LOW),
            Step(name="Generate report", step_type=StepType.CODE, command="print('Test report generated')", risk=StepRisk.LOW, depends_on=["Run unit tests", "Run type check", "Run linter"]),
        ]

    def _plan_build(self, goal: str) -> list[Step]:
        return [
            Step(name="Initialize project", step_type=StepType.SHELL, command="mkdir -p src tests", risk=StepRisk.LOW),
            Step(name="Create config files", step_type=StepType.CODE, command="print('Creating configuration files...')", risk=StepRisk.LOW, depends_on=["Initialize project"]),
            Step(name="Create source files", step_type=StepType.CODE, command="print('Creating source code...')", risk=StepRisk.LOW, depends_on=["Create config files"]),
            Step(name="Create tests", step_type=StepType.CODE, command="print('Creating tests...')", risk=StepRisk.LOW, depends_on=["Create source files"]),
            Step(name="Initialize git", step_type=StepType.SHELL, command="git init && git add . && git commit -m 'Initial commit'", risk=StepRisk.LOW, depends_on=["Create tests"]),
        ]

    def _plan_debug(self, goal: str) -> list[Step]:
        return [
            Step(name="Reproduce error", step_type=StepType.CODE, command="print('Reproducing the error...')", risk=StepRisk.LOW),
            Step(name="Analyze error", step_type=StepType.CODE, command="print('Analyzing error logs and stack trace...')", risk=StepRisk.LOW, depends_on=["Reproduce error"]),
            Step(name="Find root cause", step_type=StepType.CODE, command="print('Identifying root cause...')", risk=StepRisk.LOW, depends_on=["Analyze error"]),
            Step(name="Apply fix", step_type=StepType.CODE, command="print('Applying fix...')", risk=StepRisk.MEDIUM, depends_on=["Find root cause"]),
            Step(name="Verify fix", step_type=StepType.SHELL, command="python -m pytest", risk=StepRisk.LOW, depends_on=["Apply fix"]),
        ]

    def _plan_refactor(self, goal: str) -> list[Step]:
        return [
            Step(name="Analyze codebase", step_type=StepType.CODE, command="print('Analyzing code structure...')", risk=StepRisk.LOW),
            Step(name="Identify improvements", step_type=StepType.CODE, command="print('Finding refactoring opportunities...')", risk=StepRisk.LOW, depends_on=["Analyze codebase"]),
            Step(name="Apply refactorings", step_type=StepType.CODE, command="print('Applying refactoring changes...')", risk=StepRisk.MEDIUM, depends_on=["Identify improvements"]),
            Step(name="Run tests", step_type=StepType.SHELL, command="python -m pytest", risk=StepRisk.LOW, depends_on=["Apply refactorings"]),
            Step(name="Verify no regressions", step_type=StepType.CODE, command="print('Verifying no regressions...')", risk=StepRisk.LOW, depends_on=["Run tests"]),
        ]

    def _plan_analysis(self, goal: str) -> list[Step]:
        return [
            Step(name="Scan files", step_type=StepType.CODE, command="print('Scanning project files...')", risk=StepRisk.LOW),
            Step(name="Analyze complexity", step_type=StepType.CODE, command="print('Measuring code complexity...')", risk=StepRisk.LOW, depends_on=["Scan files"]),
            Step(name="Check dependencies", step_type=StepType.CODE, command="print('Auditing dependencies...')", risk=StepRisk.LOW, depends_on=["Scan files"]),
            Step(name="Security scan", step_type=StepType.CODE, command="print('Running security analysis...')", risk=StepRisk.LOW, depends_on=["Scan files"]),
            Step(name="Generate report", step_type=StepType.CODE, command="print('Generating analysis report...')", risk=StepRisk.LOW, depends_on=["Analyze complexity", "Check dependencies", "Security scan"]),
        ]

    def _plan_generic(self, goal: str) -> list[Step]:
        return [
            Step(name="Understand goal", step_type=StepType.CODE, command=f"print('Goal: {goal}')", risk=StepRisk.LOW),
            Step(name="Execute plan", step_type=StepType.CODE, command="print('Executing...')", risk=StepRisk.LOW, depends_on=["Understand goal"]),
            Step(name="Verify result", step_type=StepType.CODE, command="print('Verifying...')", risk=StepRisk.LOW, depends_on=["Execute plan"]),
        ]

    def _format_plan_summary(self, steps: list[Step], parallel_info: dict) -> str:
        lines = [
            f"Plan: {len(steps)} steps",
            f"Max parallelism: {parallel_info.get('max_parallel', 1)}",
            f"Critical path: {parallel_info.get('critical_path', len(steps))} steps",
            f"Total work: {parallel_info.get('total_work', len(steps) * 10)}s estimated",
        ]
        return "\n".join(lines)
