"""
JARVIS API routes package.
==========================
Defines all REST API endpoints exposed by the FastAPI server.

Routes:
    /chat      — Primary chat interface
    /skills    — Skill management and execution
    /memory    — Memory store and recall
    /system    — System status and controls
    /health    — Health check
"""

from jarvis.api.routes.chat import router as chat_router
from jarvis.api.routes.health import router as health_router
from jarvis.api.routes.skills import router as skills_router
from jarvis.api.routes.memory import router as memory_router
from jarvis.api.routes.system import router as system_router

__all__ = [
    "chat_router",
    "health_router",
    "skills_router",
    "memory_router",
    "system_router",
]
