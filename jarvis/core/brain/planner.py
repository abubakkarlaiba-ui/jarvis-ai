"""
Task planner for the JARVIS reasoning engine.
==============================================
Decomposes complex user requests into executable task plans with
dependencies, priorities, and execution strategies.

Planning modes:
    - Sequential: tasks run in order, each depends on the previous
    - Parallel: independent tasks run concurrently
    - Conditional: tasks execute based on conditions
    - ReAct: interleaved reasoning and acting (tool calls)

The planner produces a TaskPlan that the reasoning engine executes.

Usage:
    planner = TaskPlanner(settings)
    plan = await planner.create_plan(
        "Research quantum computing and write a summary",
        context=snapshot,
        tools=tool_registry,
    )
    for step in plan.steps:
        result = await execute_step(step)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from jarvis.config.settings import AISettings
from jarvis.core.brain.context import ContextSnapshot

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Execution status of a plan step."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


class StepType(Enum):
    """Types of steps in a plan."""
    REASONING = auto()    # Internal reasoning / analysis
    TOOL_CALL = auto()    # External tool invocation
    QUERY = auto()        # Information retrieval
    SYNTHESIS = auto()    # Combining information
    RESPONSE = auto()     # Final response generation


class PlanStatus(Enum):
    """Overall plan status."""
    DRAFT = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class PlanStep:
    """A single step in a task plan."""
    id: str
    step_type: StepType
    description: str
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)  # step IDs
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""
    reasoning: str = ""  # why this step is needed
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 2

    @property
    def is_ready(self) -> bool:
        """Check if all dependencies are completed."""
        return self.status == StepStatus.PENDING  # simplified

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries


@dataclass
class TaskPlan:
    """A complete task plan with ordered steps."""
    id: str
    goal: str
    steps: list[PlanStep]
    status: PlanStatus = PlanStatus.DRAFT
    context_summary: str = ""
    estimated_steps: int = 0
    completed_steps: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return completed / len(self.steps)

    @property
    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
            for s in self.steps
        )

    @property
    def failed_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    def get_step(self, step_id: str) -> PlanStep | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def get_next_step(self) -> PlanStep | None:
        """Get the next step that is ready to execute."""
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            # Check dependencies
            deps_met = all(
                self.get_step(dep_id) is not None
                and self.get_step(dep_id).status == StepStatus.COMPLETED
                for dep_id in step.depends_on
            )
            if deps_met:
                return step
        return None

    def to_summary(self) -> str:
        """Human-readable plan summary."""
        lines = [f"Plan: {self.goal}", f"Status: {self.status.name} ({self.progress:.0%})"]
        for i, step in enumerate(self.steps, 1):
            status_icon = {
                StepStatus.PENDING: "○",
                StepStatus.RUNNING: "●",
                StepStatus.COMPLETED: "✓",
                StepStatus.FAILED: "✗",
                StepStatus.SKIPPED: "−",
            }.get(step.status, "?")
            lines.append(f"  {status_icon} {i}. {step.description}")
            if step.error:
                lines.append(f"      Error: {step.error}")
        return "\n".join(lines)


class TaskPlanner:
    """Decomposes complex requests into executable task plans.

    The planner analyzes the user's request, identifies the required
    steps, determines dependencies, and produces an ordered plan.

    Planning strategy:
        1. Parse the goal into sub-tasks
        2. Identify which tools are needed
        3. Determine execution order and dependencies
        4. Estimate complexity and set priorities

    Example:
        planner = TaskPlanner(settings)
        plan = await planner.create_plan(
            "Find the latest news about AI, summarize the top 3 stories, "
            "and save them to a file called ai_news.txt",
            context=snapshot,
            tools=tool_registry,
        )
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._max_steps = settings.max_reasoning_steps

    async def create_plan(
        self,
        goal: str,
        context: ContextSnapshot | None = None,
        available_tools: list[str] | None = None,
    ) -> TaskPlan:
        """Create a task plan for the given goal.

        Args:
            goal: The user's request or objective.
            context: Current context snapshot.
            available_tools: Tools available for execution.

        Returns:
            An ordered TaskPlan with steps and dependencies.
        """
        plan = TaskPlan(
            id=str(uuid.uuid4()),
            goal=goal,
            steps=[],
            estimated_steps=0,
        )

        # Analyze the goal and decompose into steps
        steps = await self._decompose_goal(goal, context, available_tools or [])

        # Resolve dependencies
        steps = self._resolve_dependencies(steps)

        # Limit total steps
        if len(steps) > self._max_steps:
            steps = steps[:self._max_steps]
            logger.warning("Plan truncated to %d steps (max_reasoning_steps)", self._max_steps)

        plan.steps = steps
        plan.estimated_steps = len(steps)
        plan.status = PlanStatus.DRAFT

        if context:
            plan.context_summary = context.to_prompt_section()[:500]

        logger.info(
            "Task plan created: '%s' (%d steps)",
            goal[:60],
            len(steps),
        )

        return plan

    async def _decompose_goal(
        self,
        goal: str,
        context: ContextSnapshot | None,
        available_tools: list[str],
    ) -> list[PlanStep]:
        """Break a goal into concrete steps."""
        steps: list[PlanStep] = []
        goal_lower = goal.lower()

        # Step 1: Always start with understanding/analysis
        steps.append(PlanStep(
            id=str(uuid.uuid4()),
            step_type=StepType.REASONING,
            description="Analyze the request and identify requirements",
            reasoning="Understand what the user is asking before acting",
        ))

        # Detect common patterns and add appropriate steps
        needs_search = any(w in goal_lower for w in ["search", "find", "look up", "research", "latest", "news"])
        needs_file = any(w in goal_lower for w in ["save", "write", "file", "document", "export"])
        needs_summary = any(w in goal_lower for w in ["summarize", "summary", "tldr", "brief", "overview"])
        needs_analysis = any(w in goal_lower for w in ["analyze", "compare", "evaluate", "review", "explain"])
        needs_code = any(w in goal_lower for w in ["code", "program", "script", "implement", "debug"])
        needs_list = any(w in goal_lower for w in ["list", "enumerate", "options", "alternatives"])

        # Search step
        if needs_search and "search_web" in available_tools:
            steps.append(PlanStep(
                id=str(uuid.uuid4()),
                step_type=StepType.TOOL_CALL,
                description="Search for relevant information",
                tool_name="search_web",
                tool_args={"query": goal},
                reasoning="Need to gather external information",
            ))

        # Analysis step
        if needs_analysis:
            steps.append(PlanStep(
                id=str(uuid.uuid4()),
                step_type=StepType.REASONING,
                description="Analyze and process gathered information",
                reasoning="Process and structure the information for the response",
                depends_on=[s.id for s in steps if s.step_type == StepType.TOOL_CALL],
            ))

        # Summary step
        if needs_summary:
            steps.append(PlanStep(
                id=str(uuid.uuid4()),
                step_type=StepType.SYNTHESIS,
                description="Create a concise summary",
                reasoning="Condense information into a brief overview",
                depends_on=[s.id for s in steps if s.step_type in (StepType.REASONING, StepType.TOOL_CALL)],
            ))

        # Code step
        if needs_code:
            steps.append(PlanStep(
                id=str(uuid.uuid4()),
                step_type=StepType.TOOL_CALL,
                description="Generate or debug code",
                tool_name="generate_code",
                reasoning="Code generation or debugging required",
            ))

        # File save step
        if needs_file and "write_file" in available_tools:
            steps.append(PlanStep(
                id=str(uuid.uuid4()),
                step_type=StepType.TOOL_CALL,
                description="Save results to file",
                tool_name="write_file",
                reasoning="User requested file output",
                depends_on=[s.id for s in steps[-2:]] if len(steps) >= 2 else [],
            ))

        # Final response step
        steps.append(PlanStep(
            id=str(uuid.uuid4()),
            step_type=StepType.RESPONSE,
            description="Generate final response",
            reasoning="Synthesize all results into a coherent answer",
            depends_on=[s.id for s in steps if s.step_type != StepType.RESPONSE],
        ))

        return steps

    def _resolve_dependencies(self, steps: list[PlanStep]) -> list[PlanStep]:
        """Ensure dependency IDs reference valid steps."""
        step_ids = {s.id for s in steps}
        for step in steps:
            step.depends_on = [d for d in step.depends_on if d in step_ids]
        return steps

    async def update_step(
        self,
        plan: TaskPlan,
        step_id: str,
        status: StepStatus,
        result: Any = None,
        error: str = "",
    ) -> None:
        """Update a step's status and result."""
        step = plan.get_step(step_id)
        if not step:
            return

        step.status = status
        step.result = result
        step.error = error

        if status == StepStatus.COMPLETED:
            plan.completed_steps += 1
        elif status == StepStatus.FAILED and step.can_retry:
            step.retry_count += 1
            step.status = StepStatus.PENDING
            logger.info("Step '%s' will retry (%d/%d)", step.description, step.retry_count, step.max_retries)

        # Check if plan is complete
        if plan.is_complete:
            plan.status = PlanStatus.COMPLETED
        elif any(s.status == StepStatus.FAILED for s in plan.steps) and not any(
            s.status == StepStatus.PENDING for s in plan.steps
        ):
            plan.status = PlanStatus.FAILED

    def estimate_complexity(self, goal: str) -> str:
        """Estimate the complexity of a goal.

        Returns: "simple", "moderate", or "complex"
        """
        word_count = len(goal.split())
        has_multiple = any(phrase in goal.lower() for phrase in [
            " and ", " then ", " also ", " additionally ", "Furthermore",
            "first", "second", "finally", "step",
        ])
        has_search = any(w in goal.lower() for w in ["search", "find", "research"])
        has_file = any(w in goal.lower() for w in ["file", "save", "write"])

        score = 0
        if word_count > 10:
            score += 1
        if has_multiple:
            score += 1
        if has_search:
            score += 1
        if has_file:
            score += 1

        if score <= 1:
            return "simple"
        elif score <= 3:
            return "moderate"
        return "complex"
