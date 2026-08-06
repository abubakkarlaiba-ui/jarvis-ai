"""
Skills module — plugin system for extensible functionality.
==========================================================
Every feature in JARVIS is a skill that can be loaded, configured, and executed.

Architecture:
    SkillRegistry  →  SkillLoader  →  SkillInstance
         ↑                 ↑                ↑
    skill metadata    dynamic import    lifecycle mgmt

Usage:
    # Define a custom skill
    class WeatherSkill(BaseSkill):
        name = "weather"
        async def execute(self, context): return "Sunny, 22C"

    # Register and run
    registry = SkillRegistry()
    registry.register(WeatherSkill)
    result = await registry.execute("weather", context)
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SkillState(Enum):
    """Lifecycle state of a skill."""
    UNLOADED = auto()
    LOADED = auto()
    INITIALIZED = auto()
    RUNNING = auto()
    ERROR = auto()
    DISABLED = auto()


@dataclass
class SkillMetadata:
    """Metadata describing a skill's capabilities and requirements."""
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    required_features: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class SkillContext:
    """Execution context passed to a skill."""
    user_input: str
    parameters: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result returned by a skill execution."""
    success: bool
    output: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """Base class all JARVIS skills must inherit from.

    Provides lifecycle hooks and a standardized execution interface.

    Example:
        class TimeSkill(BaseSkill):
            metadata = SkillMetadata(name="time", description="Tell current time")

            async def on_initialize(self): pass
            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True, output=datetime.now().isoformat())
            async def on_shutdown(self): pass
    """

    metadata: SkillMetadata = SkillMetadata(name="unnamed")

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute the skill with the given context.

        Args:
            context: Execution context with user input and parameters.

        Returns:
            SkillResult with the outcome of the execution.
        """
        ...

    async def on_initialize(self) -> None:
        """Called once when the skill is first loaded. Override for setup logic."""
        pass

    async def on_shutdown(self) -> None:
        """Called when JARVIS is shutting down. Override for cleanup logic."""
        pass

    async def on_enable(self) -> None:
        """Called when the skill is enabled."""
        pass

    async def on_disable(self) -> None:
        """Called when the skill is disabled."""
        pass


class SkillRegistry:
    """Central registry for all loaded skills.

    Manages skill discovery, registration, lifecycle, and execution routing.

    Example:
        registry = SkillRegistry()
        registry.register_class(WeatherSkill)
        result = await registry.execute("weather", context)
    """

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}
        self._metadata: dict[str, SkillMetadata] = {}
        self._states: dict[str, SkillState] = {}

    def register_class(self, skill_class: type[BaseSkill]) -> None:
        """Register a skill class and create its instance.

        Args:
            skill_class: The BaseSkill subclass to register.

        Raises:
            ValueError: If a skill with the same name is already registered.
        """
        instance = skill_class()
        name = instance.metadata.name
        if name in self._skills:
            raise ValueError(f"Skill '{name}' is already registered")

        self._skills[name] = instance
        self._metadata[name] = instance.metadata
        self._states[name] = SkillState.LOADED
        logger.info("Registered skill: %s (v%s)", name, instance.metadata.version)

    def register_instance(self, skill: BaseSkill) -> None:
        """Register a pre-instantiated skill.

        Args:
            skill: An existing BaseSkill instance.

        Raises:
            ValueError: If a skill with the same name is already registered.
        """
        name = skill.metadata.name
        if name in self._skills:
            raise ValueError(f"Skill '{name}' is already registered")

        self._skills[name] = skill
        self._metadata[name] = skill.metadata
        self._states[name] = SkillState.LOADED
        logger.info("Registered skill instance: %s", name)

    async def initialize_all(self) -> None:
        """Initialize all registered skills."""
        for name, skill in self._skills.items():
            try:
                await skill.on_initialize()
                self._states[name] = SkillState.INITIALIZED
                logger.debug("Initialized skill: %s", name)
            except Exception as exc:
                self._states[name] = SkillState.ERROR
                logger.error("Failed to initialize skill '%s': %s", name, exc)

    async def execute(self, skill_name: str, context: SkillContext) -> SkillResult:
        """Execute a skill by name.

        Args:
            skill_name: Name of the skill to execute.
            context: Execution context.

        Returns:
            SkillResult with the outcome.

        Raises:
            KeyError: If no skill is registered with the given name.
        """
        if skill_name not in self._skills:
            return SkillResult(
                success=False,
                error=f"Skill '{skill_name}' not found",
            )

        skill = self._skills[skill_name]
        state = self._states[skill_name]

        if state == SkillState.DISABLED:
            return SkillResult(success=False, error=f"Skill '{skill_name}' is disabled")
        if state == SkillState.ERROR:
            return SkillResult(success=False, error=f"Skill '{skill_name}' is in error state")

        try:
            self._states[skill_name] = SkillState.RUNNING
            result = await skill.execute(context)
            self._states[skill_name] = SkillState.INITIALIZED
            return result
        except Exception as exc:
            self._states[skill_name] = SkillState.ERROR
            logger.error("Skill '%s' execution failed: %s", skill_name, exc)
            return SkillResult(success=False, error=str(exc))

    async def shutdown_all(self) -> None:
        """Shutdown all registered skills gracefully."""
        for name, skill in self._skills.items():
            try:
                await skill.on_shutdown()
                self._states[name] = SkillState.UNLOADED
            except Exception as exc:
                logger.error("Error shutting down skill '%s': %s", name, exc)

    def enable(self, skill_name: str) -> bool:
        """Enable a skill. Returns True if successful."""
        if skill_name in self._skills:
            self._states[skill_name] = SkillState.INITIALIZED
            logger.info("Enabled skill: %s", skill_name)
            return True
        return False

    def disable(self, skill_name: str) -> bool:
        """Disable a skill. Returns True if successful."""
        if skill_name in self._skills:
            self._states[skill_name] = SkillState.DISABLED
            logger.info("Disabled skill: %s", skill_name)
            return True
        return False

    def list_skills(self) -> list[dict[str, Any]]:
        """Return metadata for all registered skills."""
        return [
            {
                "name": name,
                "version": self._metadata[name].version,
                "description": self._metadata[name].description,
                "state": self._states[name].name,
                "tags": self._metadata[name].tags,
            }
            for name in self._skills
        ]

    def get_skill(self, name: str) -> BaseSkill | None:
        """Return a skill instance by name, or None if not found."""
        return self._skills.get(name)


class SkillLoader:
    """Dynamic skill loader that discovers and imports skill modules.

    Scans directories for Python files containing BaseSkill subclasses
    and registers them automatically.

    Example:
        loader = SkillLoader(registry)
        await loader.load_from_directory("plugins/")
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    async def load_from_directory(self, directory: str) -> int:
        """Load all skills from Python files in a directory.

        Args:
            directory: Path to scan for skill modules.

        Returns:
            Number of skills successfully loaded.
        """
        plugin_dir = Path(directory)
        if not plugin_dir.exists():
            logger.warning("Plugin directory does not exist: %s", directory)
            return 0

        loaded = 0
        for py_file in plugin_dir.glob("**/*.skill.py"):
            try:
                count = await self._load_module(py_file)
                loaded += count
            except Exception as exc:
                logger.error("Failed to load skill from %s: %s", py_file, exc)

        logger.info("Loaded %d skills from %s", loaded, directory)
        return loaded

    async def _load_module(self, module_path: Path) -> int:
        """Import a module and register any BaseSkill subclasses found."""
        module_name = f"jarvis_skill_{module_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            return 0

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        count = 0
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseSkill)
                and attr is not BaseSkill
            ):
                try:
                    self.registry.register_class(attr)
                    count += 1
                except ValueError as exc:
                    logger.warning("Skipped skill: %s", exc)

        return count
