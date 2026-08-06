"""
FastAPI application factory for JARVIS.
=======================================
Creates and configures the ASGI application with all routes and middleware.

Usage:
    # Run with uvicorn
    uvicorn jarvis.api.app:app --host 0.0.0.0 --port 8000

    # Or use the startup script
    python -m jarvis.main
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jarvis.config import get_settings, get_container
from jarvis.core.brain.engine import ReasoningEngine
from jarvis.core.brain.module import BrainModule
from jarvis.core.voice import VoiceModule
from jarvis.core.memory import MemoryModule
from jarvis.core.vision import VisionModule
from jarvis.core.automation import AutomationModule
from jarvis.core.skills import SkillRegistry, SkillLoader
from jarvis.api.middleware import RequestLoggingMiddleware, APIKeyMiddleware
from jarvis.api.routes import (
    chat_router,
    health_router,
    skills_router,
    memory_router,
    system_router,
)
from jarvis.utils.logger import setup_logging

logger = logging.getLogger(__name__)

_start_time: float = time.time()


def get_start_time() -> float:
    """Return the application start time."""
    return _start_time


@dataclass
class JarvisCore:
    """Central container holding all JARVIS module instances.

    Provides a single access point for all core subsystems.
    """
    brain: BrainModule | None = None
    reasoning: ReasoningEngine | None = None
    voice: VoiceModule | None = None
    memory: MemoryModule | None = None
    vision: VisionModule | None = None
    automation: AutomationModule | None = None
    skills: SkillRegistry | None = None
    settings: Any = None
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)


_core: JarvisCore | None = None


def get_jarvis_core() -> JarvisCore:
    """Return the global JarvisCore instance."""
    global _core
    if _core is None:
        raise RuntimeError("JARVIS core not initialized. Call create_app() first.")
    return _core


async def _initialize_modules(settings: Any) -> JarvisCore:
    """Initialize all core modules and wire up dependencies.

    Args:
        settings: Application settings instance.

    Returns:
        Initialized JarvisCore instance.
    """
    core = JarvisCore(settings=settings)

    # Reasoning Engine — the central AI brain
    core.reasoning = ReasoningEngine(settings.ai)
    await core.reasoning.initialize()
    logger.info("ReasoningEngine initialized")

    # Legacy brain (kept for backward compatibility)
    core.brain = BrainModule()
    logger.info("Legacy BrainModule initialized")

    # Voice
    core.voice = VoiceModule()
    await core.voice.initialize()
    logger.info("Voice module initialized")

    # Memory
    core.memory = MemoryModule(settings.memory)
    logger.info("Memory module initialized")

    # Vision
    core.vision = VisionModule(settings.vision)
    await core.vision.initialize()
    logger.info("Vision module initialized")

    # Automation
    core.automation = AutomationModule(settings.automation)
    await core.automation.initialize()
    logger.info("Automation module initialized")

    # Skills
    core.skills = SkillRegistry()
    loader = SkillLoader(core.skills)
    from jarvis.utils.helpers import ensure_directory
    plugins_dir = ensure_directory("plugins")
    await loader.load_from_directory(str(plugins_dir))
    await core.skills.initialize_all()
    logger.info("Skills module initialized with %d skills", len(core.skills.list_skills()))

    return core


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — startup and shutdown hooks.

    Initializes all modules on startup and cleans up on shutdown.
    """
    global _core, _start_time
    _start_time = time.time()

    settings = get_settings()
    setup_logging(
        level=settings.logging.level,
        log_format=settings.logging.format,
        log_file=settings.logging.file_path,
        console_output=settings.logging.console_output,
    )

    logger.info("JARVIS v%s starting up (env=%s)", settings.version, settings.environment)

    _core = await _initialize_modules(settings)

    # Register core in DI container
    container = get_container()
    container.register("brain", lambda: _core.brain, singleton=True, type_hint=BrainModule)
    container.register("reasoning", lambda: _core.reasoning, singleton=True, type_hint=ReasoningEngine)
    container.register("voice", lambda: _core.voice, singleton=True, type_hint=VoiceModule)
    container.register("memory", lambda: _core.memory, singleton=True, type_hint=MemoryModule)
    container.register("vision", lambda: _core.vision, singleton=True, type_hint=VisionModule)
    container.register("automation", lambda: _core.automation, singleton=True, type_hint=AutomationModule)
    container.register("skills", lambda: _core.skills, singleton=True, type_hint=SkillRegistry)

    logger.info("JARVIS is online. All systems nominal.")

    yield

    # Shutdown
    logger.info("JARVIS shutting down...")
    if _core.reasoning:
        await _core.reasoning.shutdown()
    if _core.skills:
        await _core.skills.shutdown_all()
    if _core.voice:
        await _core.voice.cleanup()
    if _core.vision:
        await _core.vision.cleanup()
    if _core.automation:
        await _core.automation.cleanup()
    logger.info("JARVIS shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured FastAPI instance ready to serve.
    """
    settings = get_settings()

    app = FastAPI(
        title="JARVIS AI Assistant",
        version=settings.version,
        description="Production-ready desktop AI assistant API",
        lifespan=lifespan,
    )

    # Middleware — applied in reverse order (last added = first executed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(APIKeyMiddleware, api_key=settings.api.api_key)
    app.add_middleware(RequestLoggingMiddleware)

    # Routes
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(skills_router)
    app.include_router(memory_router)
    app.include_router(system_router)

    return app


app = create_app()
