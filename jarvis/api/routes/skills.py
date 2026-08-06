"""
Skills route — manage, install, remove, and execute skills.
==========================================================
Provides full CRUD for the JARVIS skill ecosystem.
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


# ── Request / Response models ─────────────────────────────────────


class SkillInfo(BaseModel):
    name: str
    version: str
    description: str
    state: str
    tags: list[str]


class SkillListResponse(BaseModel):
    skills: list[SkillInfo]
    total: int


class SkillDetailResponse(BaseModel):
    name: str
    version: str
    description: str
    author: str
    state: str
    tags: list[str]
    installed: bool = False
    disabled: bool = False
    installed_at: str | None = None
    file_hash: str | None = None


class SkillExecuteRequest(BaseModel):
    skill_name: str = Field(..., description="Name of the skill to execute")
    user_input: str = Field(default="", description="User input for the skill")
    parameters: dict = Field(default_factory=dict, description="Skill parameters")
    session_id: str = Field(default="", description="Session identifier")


class SkillExecuteResponse(BaseModel):
    success: bool
    output: dict | str | list | None = None
    error: str = ""


class SkillInstallRequest(BaseModel):
    source_path: str = Field(..., description="Local path to the .skill.py file")
    name: str | None = Field(default=None, description="Override skill name")


class SkillSearchResponse(BaseModel):
    query: str
    results: list[SkillInfo]
    total: int


class SkillStatsResponse(BaseModel):
    total: int
    enabled: int
    disabled: int
    error: int
    installed: int


# ── Dependency helper ─────────────────────────────────────────────


def _get_skill_manager():
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    if not hasattr(core, "skill_manager"):
        raise HTTPException(status_code=503, detail="Skill manager not initialized")
    return core.skill_manager


def _get_registry():
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    return core.skills


# ── List / Detail ─────────────────────────────────────────────────


@router.get("/", response_model=SkillListResponse)
async def list_skills() -> SkillListResponse:
    """List all registered skills."""
    registry = _get_registry()
    skills = registry.list_skills()
    return SkillListResponse(
        skills=[SkillInfo(**s) for s in skills],
        total=len(skills),
    )


@router.get("/{skill_name}", response_model=SkillDetailResponse)
async def get_skill(skill_name: str) -> SkillDetailResponse:
    """Get detailed info for a specific skill."""
    mgr = _get_skill_manager()
    info = mgr.get_skill_info(skill_name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    return SkillDetailResponse(**info)


# ── Execute ───────────────────────────────────────────────────────


@router.post("/execute", response_model=SkillExecuteResponse)
async def execute_skill(request: SkillExecuteRequest) -> SkillExecuteResponse:
    """Execute a registered skill by name."""
    from jarvis.core.skills import SkillContext

    registry = _get_registry()
    context = SkillContext(
        user_input=request.user_input,
        parameters=request.parameters,
        session_id=request.session_id,
    )
    result = await registry.execute(request.skill_name, context)

    output = result.output
    if hasattr(output, "__dict__"):
        output = vars(output)

    return SkillExecuteResponse(
        success=result.success,
        output=output,
        error=result.error,
    )


# ── Install / Remove ──────────────────────────────────────────────


@router.post("/install")
async def install_skill(request: SkillInstallRequest) -> dict:
    """Install a skill from a local .skill.py file."""
    mgr = _get_skill_manager()
    result = await mgr.install_skill(request.source_path, request.name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Install failed"))
    return result


@router.post("/{skill_name}/remove")
async def remove_skill(skill_name: str) -> dict:
    """Remove an installed skill."""
    mgr = _get_skill_manager()
    result = await mgr.remove_skill(skill_name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Remove failed"))
    return result


# ── Enable / Disable ──────────────────────────────────────────────


@router.post("/{skill_name}/enable")
async def enable_skill(skill_name: str) -> dict:
    """Enable a skill."""
    mgr = _get_skill_manager()
    result = mgr.enable_skill(skill_name)
    return result


@router.post("/{skill_name}/disable")
async def disable_skill(skill_name: str) -> dict:
    """Disable a skill."""
    mgr = _get_skill_manager()
    result = mgr.disable_skill(skill_name)
    return result


# ── Search / Stats ────────────────────────────────────────────────


@router.get("/search/{query}", response_model=SkillSearchResponse)
async def search_skills(query: str) -> SkillSearchResponse:
    """Search skills by name, description, or tags."""
    mgr = _get_skill_manager()
    results = mgr.search_skills(query)
    return SkillSearchResponse(
        query=query,
        results=[SkillInfo(**s) for s in results],
        total=len(results),
    )


@router.get("/stats/overview", response_model=SkillStatsResponse)
async def skill_stats() -> SkillStatsResponse:
    """Get skill ecosystem statistics."""
    mgr = _get_skill_manager()
    return SkillStatsResponse(**mgr.stats())


@router.post("/discover")
async def discover_skills() -> dict:
    """Re-scan plugins directory for new or updated skills."""
    mgr = _get_skill_manager()
    skills = await mgr.discover_skills()
    return {"discovered": len(skills), "skills": skills}
