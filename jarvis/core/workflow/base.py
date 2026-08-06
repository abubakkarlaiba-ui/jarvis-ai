"""
Workflow Engine — base types and configuration.
================================================
Shared dataclasses, enums, and settings for the workflow execution engine.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable


class StepStatus(Enum):
    """Lifecycle status of a workflow step."""
    PENDING = auto()
    WAITING = auto()       # waiting for dependencies
    READY = auto()         # dependencies met, ready to run
    RUNNING = auto()
    PAUSED = auto()
    CONFIRMATION = auto()  # waiting for user confirmation
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()
    CANCELLED = auto()
    RETRYING = auto()


class WorkflowStatus(Enum):
    """Overall workflow status."""
    CREATED = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    INTERRUPTED = auto()   # can be resumed


class StepType(Enum):
    """Types of steps the engine can execute."""
    CODE = "code"           # execute Python code
    SHELL = "shell"         # execute shell command
    HTTP = "http"           # make HTTP request
    FILE = "file"           # file operations
    SKILL = "skill"         # invoke a JARVIS skill
    WORKFLOW = "workflow"   # nested sub-workflow
    CONDITION = "condition" # if/else branching
    LOOP = "loop"           # repeat steps
    WAIT = "wait"           # wait for duration or event
    MANUAL = "manual"       # requires human action
    CALLBACK = "callback"   # call a registered function


class StepRisk(Enum):
    """Risk level for confirmation prompts."""
    LOW = auto()        # no confirmation needed
    MEDIUM = auto()     # confirmation recommended
    HIGH = auto()       # confirmation required
    DESTRUCTIVE = auto() # double confirmation required


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: str = ""
    status: StepStatus = StepStatus.SUCCESS
    output: Any = None
    error: str = ""
    duration: float = 0.0
    retries: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Step:
    """A single step in a workflow.

    Steps can depend on other steps, have retry policies,
    and require confirmation before execution.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    step_type: StepType = StepType.CODE
    risk: StepRisk = StepRisk.LOW

    # Execution config
    command: str = ""           # code, shell command, URL, or skill name
    params: dict[str, Any] = field(default_factory=dict)
    timeout: float = 300.0      # seconds

    # Dependencies
    depends_on: list[str] = field(default_factory=list)

    # Retry policy
    max_retries: int = 0
    retry_delay: float = 1.0    # seconds
    retry_backoff: float = 2.0  # exponential multiplier

    # Runtime state
    status: StepStatus = StepStatus.PENDING
    result: StepResult | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class Workflow:
    """A complete workflow containing ordered steps.

    Workflows track execution state, support pause/resume,
    and persist to disk for recovery.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    steps: list[Step] = field(default_factory=list)

    # Status
    status: WorkflowStatus = WorkflowStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Configuration
    variables: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    auto_retry: bool = True
    pause_on_error: bool = False

    # Runtime
    current_step_index: int = 0
    results: list[StepResult] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class WorkflowPlan:
    """A decomposed plan for executing a high-level goal."""
    goal: str = ""
    steps: list[Step] = field(default_factory=list)
    estimated_duration: float = 0.0  # seconds
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    parallel_groups: list[list[str]] = field(default_factory=list)
    summary: str = ""


@dataclass
class ProgressUpdate:
    """Progress information for a running workflow."""
    workflow_id: str = ""
    workflow_name: str = ""
    status: WorkflowStatus = WorkflowStatus.RUNNING
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    current_step: str = ""
    percent: float = 0.0
    eta_seconds: float = 0.0
    elapsed_seconds: float = 0.0
    message: str = ""


@dataclass
class LogEntry:
    """A single log entry for workflow execution."""
    timestamp: datetime = field(default_factory=datetime.now)
    workflow_id: str = ""
    step_id: str = ""
    level: str = "INFO"
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
