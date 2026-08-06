"""
System route — system-level controls for JARVIS.
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


class SystemStatusResponse(BaseModel):
    """Detailed system status."""
    version: str
    environment: str
    debug: bool
    modules: dict[str, dict]
    memory_stats: dict[str, int]


@router.get("/status", response_model=SystemStatusResponse)
async def system_status() -> SystemStatusResponse:
    """Return detailed system status including all module states."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()

    modules = {}
    for name in ["brain", "voice", "memory", "vision", "automation", "skills"]:
        module = getattr(core, name, None)
        modules[name] = {
            "initialized": module is not None,
            "type": type(module).__name__ if module else None,
        }

    memory_stats = await core.memory.get_stats() if core.memory else {}

    return SystemStatusResponse(
        version=core.settings.version,
        environment=core.settings.environment,
        debug=core.settings.debug,
        modules=modules,
        memory_stats=memory_stats,
    )


@router.post("/shutdown")
async def shutdown() -> dict:
    """Gracefully shut down JARVIS.

    Triggers cleanup of all modules and saves state.
    """
    import asyncio
    from jarvis.api.app import get_jarvis_core

    core = get_jarvis_core()
    logger.info("Shutdown requested via API")

    asyncio.get_event_loop().call_soon(core.shutdown_event.set)

    return {"message": "Shutdown initiated"}


@router.post("/memory/clear")
async def clear_memory(layer: str = "short_term") -> dict:
    """Clear the specified memory layer."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()

    if layer == "short_term":
        core.memory.short_term.clear()
    elif layer == "all":
        core.memory.short_term.clear()
        core.memory.vector.clear()

    return {"success": True, "cleared": layer}
