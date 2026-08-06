"""
Workflow Engine route — autonomous task execution API.
======================================================
Exposes workflow planning, execution, monitoring, and control.
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["workflow"])


# ── Request / Response models ─────────────────────────────────────


class StepModel(BaseModel):
    name: str = ""
    description: str = ""
    step_type: str = Field(default="code", description="code, shell, http, file, skill, condition, loop, wait, manual")
    risk: str = Field(default="low", description="low, medium, high, destructive")
    command: str = Field(default="", description="Command, code, URL, or skill name")
    params: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    max_retries: int = Field(default=0)
    retry_delay: float = Field(default=1.0)
    timeout: float = Field(default=300.0)
    tags: list[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    goal: str = Field(..., description="Natural language goal to plan")
    name: str = Field(default="", description="Workflow name")


class PlanResponse(BaseModel):
    goal: str
    steps: list[dict]
    estimated_duration: float
    dependencies: dict[str, list[str]]
    parallel_groups: list[list[str]]
    summary: str


class ExecutePlanRequest(BaseModel):
    goal: str = Field(..., description="Goal to execute")
    name: str = Field(default="")
    auto_confirm: bool = Field(default=False, description="Auto-approve risky steps")


class ExecuteWorkflowRequest(BaseModel):
    workflow_id: str = Field(..., description="Workflow ID to execute")


class CreateWorkflowRequest(BaseModel):
    name: str = Field(..., description="Workflow name")
    description: str = Field(default="")
    steps: list[StepModel] = Field(..., description="Workflow steps")
    variables: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    confirmation_id: str = Field(..., description="Confirmation ID")
    approved: bool = Field(..., description="Whether to approve")
    message: str = Field(default="")


class RetryStepRequest(BaseModel):
    workflow_id: str
    step_id: str


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    total_steps: int
    completed_steps: int = 0
    failed_steps: int = 0
    current_step: str = ""
    percent: float = 0.0
    eta_seconds: float = 0.0
    error: str = ""
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None


class ProgressResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    status: str
    total_steps: int
    completed_steps: int
    failed_steps: int
    current_step: str
    percent: float
    eta_seconds: float
    elapsed_seconds: float
    message: str


class LogEntryResponse(BaseModel):
    timestamp: str
    level: str
    message: str
    step_id: str = ""
    data: dict = {}


class StatsResponse(BaseModel):
    total: int
    running: int
    completed: int
    failed: int


# ── Dependency helper ─────────────────────────────────────────────


def _get_engine():
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    if not hasattr(core, "workflow_engine"):
        raise HTTPException(status_code=503, detail="Workflow engine not initialized")
    return core.workflow_engine


def _step_model_to_step(model: StepModel):
    from jarvis.core.workflow.base import Step, StepType, StepRisk
    type_map = {
        "code": StepType.CODE, "shell": StepType.SHELL, "http": StepType.HTTP,
        "file": StepType.FILE, "skill": StepType.SKILL, "workflow": StepType.WORKFLOW,
        "condition": StepType.CONDITION, "loop": StepType.LOOP, "wait": StepType.WAIT,
        "manual": StepType.MANUAL, "callback": StepType.CALLBACK,
    }
    risk_map = {
        "low": StepRisk.LOW, "medium": StepRisk.MEDIUM,
        "high": StepRisk.HIGH, "destructive": StepRisk.DESTRUCTIVE,
    }
    return Step(
        name=model.name,
        description=model.description,
        step_type=type_map.get(model.step_type, StepType.CODE),
        risk=risk_map.get(model.risk, StepRisk.LOW),
        command=model.command,
        params=model.params,
        depends_on=model.depends_on,
        max_retries=model.max_retries,
        retry_delay=model.retry_delay,
        timeout=model.timeout,
        tags=model.tags,
    )


def _workflow_to_response(workflow) -> WorkflowResponse:
    from jarvis.core.workflow.base import WorkflowStatus
    completed = sum(1 for s in workflow.steps if s.status.name == "SUCCESS")
    failed = sum(1 for s in workflow.steps if s.status.name == "FAILED")
    current = next(
        (s.name for s in workflow.steps if s.status.name in ("RUNNING", "READY", "WAITING")),
        "",
    )
    total = len(workflow.steps)
    percent = (completed / total * 100) if total > 0 else 0
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status.name,
        total_steps=total,
        completed_steps=completed,
        failed_steps=failed,
        current_step=current,
        percent=percent,
        error=workflow.error,
        created_at=workflow.created_at.isoformat() if workflow.created_at else "",
        started_at=workflow.started_at.isoformat() if workflow.started_at else None,
        completed_at=workflow.completed_at.isoformat() if workflow.completed_at else None,
    )


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/plan", response_model=PlanResponse)
async def plan_workflow(request: PlanRequest) -> PlanResponse:
    """Decompose a goal into an executable workflow plan."""
    engine = _get_engine()
    plan = await engine.plan_from_goal(request.goal)
    steps_dicts = []
    for s in plan.steps:
        steps_dicts.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "type": s.step_type.value,
            "risk": s.risk.name,
            "depends_on": s.depends_on,
            "max_retries": s.max_retries,
        })
    return PlanResponse(
        goal=plan.goal,
        steps=steps_dicts,
        estimated_duration=plan.estimated_duration,
        dependencies=plan.dependencies,
        parallel_groups=plan.parallel_groups,
        summary=plan.summary,
    )


@router.post("/execute", response_model=WorkflowResponse)
async def execute_plan(request: ExecutePlanRequest) -> WorkflowResponse:
    """Plan and execute a goal in one step."""
    engine = _get_engine()
    plan = await engine.plan_from_goal(request.goal)
    workflow = await engine.execute_plan(plan, name=request.name, auto_confirm=request.auto_confirm)
    return _workflow_to_response(workflow)


@router.post("/create", response_model=WorkflowResponse)
async def create_workflow(request: CreateWorkflowRequest) -> WorkflowResponse:
    """Create a workflow from explicit steps."""
    engine = _get_engine()
    steps = [_step_model_to_step(s) for s in request.steps]
    workflow = engine.create_workflow(
        name=request.name,
        steps=steps,
        description=request.description,
        variables=request.variables,
        tags=request.tags,
    )
    return _workflow_to_response(workflow)


@router.post("/{workflow_id}/run", response_model=WorkflowResponse)
async def run_workflow(workflow_id: str) -> WorkflowResponse:
    """Execute a created workflow by ID."""
    engine = _get_engine()
    workflow = engine.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    result = await engine.run_workflow(workflow)
    return _workflow_to_response(result)


@router.post("/{workflow_id}/pause")
async def pause_workflow(workflow_id: str) -> dict:
    """Pause a running workflow."""
    engine = _get_engine()
    success = await engine.pause_workflow(workflow_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot pause workflow")
    return {"workflow_id": workflow_id, "paused": True}


@router.post("/{workflow_id}/resume", response_model=WorkflowResponse)
async def resume_workflow(workflow_id: str) -> WorkflowResponse:
    """Resume a paused or interrupted workflow."""
    engine = _get_engine()
    workflow = await engine.resume_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=400, detail="Cannot resume workflow")
    return _workflow_to_response(workflow)


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str) -> dict:
    """Cancel a running workflow."""
    engine = _get_engine()
    success = await engine.cancel_workflow(workflow_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel workflow")
    return {"workflow_id": workflow_id, "cancelled": True}


@router.post("/{workflow_id}/retry-step", response_model=WorkflowResponse)
async def retry_step(request: RetryStepRequest) -> WorkflowResponse:
    """Retry a failed step in a workflow."""
    engine = _get_engine()
    result = await engine.retry_step(request.workflow_id, request.step_id)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot retry step")
    workflow = engine.get_workflow(request.workflow_id)
    return _workflow_to_response(workflow)


@router.get("/list", response_model=list[WorkflowResponse])
async def list_workflows(status: str | None = None, limit: int = 50) -> list[WorkflowResponse]:
    """List all workflows."""
    engine = _get_engine()
    from jarvis.core.workflow.base import WorkflowStatus
    status_enum = None
    if status:
        try:
            status_enum = WorkflowStatus[status.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    workflows = engine.list_workflows(status_enum, limit)
    return [WorkflowResponse(**w) for w in workflows]


@router.get("/resumable", response_model=list[WorkflowResponse])
async def get_resumable() -> list[WorkflowResponse]:
    """Get workflows that can be resumed."""
    engine = _get_engine()
    resumable = engine.get_resumable()
    return [WorkflowResponse(**w) for w in resumable]


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get workflow engine statistics."""
    engine = _get_engine()
    return StatsResponse(**engine.get_stats())


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str) -> WorkflowResponse:
    """Get a specific workflow by ID."""
    engine = _get_engine()
    workflow = engine.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return _workflow_to_response(workflow)


@router.get("/{workflow_id}/progress", response_model=ProgressResponse)
async def get_progress(workflow_id: str) -> ProgressResponse:
    """Get progress information for a workflow."""
    engine = _get_engine()
    progress = engine.get_progress(workflow_id)
    return ProgressResponse(
        workflow_id=progress.workflow_id,
        workflow_name=progress.workflow_name,
        status=progress.status.name,
        total_steps=progress.total_steps,
        completed_steps=progress.completed_steps,
        failed_steps=progress.failed_steps,
        current_step=progress.current_step,
        percent=progress.percent,
        eta_seconds=progress.eta_seconds,
        elapsed_seconds=progress.elapsed_seconds,
        message=progress.message,
    )


@router.get("/{workflow_id}/logs", response_model=list[LogEntryResponse])
async def get_logs(workflow_id: str, level: str | None = None) -> list[LogEntryResponse]:
    """Get execution logs for a workflow."""
    engine = _get_engine()
    logs = engine.get_logs(workflow_id, level)
    return [
        LogEntryResponse(
            timestamp=log.timestamp.isoformat(),
            level=log.level,
            message=log.message,
            step_id=log.step_id,
            data=log.data,
        )
        for log in logs
    ]


@router.post("/confirm")
async def confirm_step(request: ConfirmRequest) -> dict:
    """Respond to a confirmation prompt."""
    engine = _get_engine()
    result = engine.confirmations.confirm(request.confirmation_id, request.approved, request.message)
    return {"confirmation_id": request.confirmation_id, "approved": result}
