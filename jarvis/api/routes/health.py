"""
Health check route — monitors system status.
"""

from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["health"])

_HTML_PATH = Path(__file__).resolve().parent.parent.parent / "ui" / "templates" / "index.html"


@router.get("/", response_class=HTMLResponse)
async def root():
    """Serve the JARVIS frontend."""
    return HTMLResponse(content=_HTML_PATH.read_text(encoding="utf-8"))


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy")
    version: str
    uptime_seconds: float
    modules: dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the current health status of JARVIS.

    Reports on each core module's availability and overall system uptime.
    """
    import time
    from jarvis.api.app import get_jarvis_core, get_start_time

    core = get_jarvis_core()
    uptime = time.time() - get_start_time()

    modules = {}
    if core.brain:
        modules["brain"] = "healthy"
    if core.voice:
        modules["voice"] = "healthy"
    if core.memory:
        modules["memory"] = "healthy"
    if core.vision:
        modules["vision"] = "healthy"
    if core.automation:
        modules["automation"] = "healthy"
    if core.skills:
        modules["skills"] = "healthy"

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        uptime_seconds=round(uptime, 2),
        modules=modules,
    )
