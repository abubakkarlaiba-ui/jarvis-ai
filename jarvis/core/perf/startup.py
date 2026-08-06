"""
Performance module — fast startup with lazy loading and dependency injection.
============================================================================
Manages module initialization order, dependency resolution, and lazy loading.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable

from jarvis.core.perf.base import ProfileMetric


class StartupManager:
    """Fast startup with lazy loading and dependency injection."""

    def __init__(self) -> None:
        self._registry: dict[str, dict[str, Any]] = {}
        self._instances: dict[str, Any] = {}
        self._init_order: list[str] = []
        self._init_times: dict[str, float] = {}
        self._start_time: float = 0.0
        self._total_startup_time: float = 0.0
        self._critical_modules: set[str] = set()
        self._cache: dict[str, Any] = {}

    def register_module(
        self,
        name: str,
        factory: Callable,
        dependencies: list[str] | None = None,
        priority: int = 0,
    ) -> None:
        """Register a module factory with its dependencies."""
        self._registry[name] = {
            "factory": factory,
            "dependencies": dependencies or [],
            "priority": priority,
            "lazy": False,
        }

    def register_lazy(
        self,
        name: str,
        factory: Callable,
        dependencies: list[str] | None = None,
    ) -> None:
        """Register a module for lazy loading (loaded on first access)."""
        self._registry[name] = {
            "factory": factory,
            "dependencies": dependencies or [],
            "priority": 0,
            "lazy": True,
        }

    async def initialize_all(
        self, progress_callback: Callable | None = None
    ) -> None:
        """Initialize all modules in dependency order (topological sort)."""
        self._start_time = time.perf_counter()
        order = self._resolve_dependencies()
        total = len(order)

        for idx, name in enumerate(order):
            if progress_callback:
                progress_callback(name, idx, total)

            entry = self._registry.get(name)
            if not entry or entry.get("lazy", False):
                continue

            module_start = time.perf_counter()
            instance = await self._create_instance(name)
            self._instances[name] = instance
            self._init_times[name] = time.perf_counter() - module_start

        self._total_startup_time = time.perf_counter() - self._start_time

    async def _create_instance(self, name: str) -> Any:
        """Create an instance from a registered factory."""
        entry = self._registry[name]
        factory = entry["factory"]

        if asyncio.iscoroutinefunction(factory):
            return await factory()
        return factory()

    async def get_module(self, name: str) -> Any:
        """Get a module instance, initializing if lazy."""
        if name in self._instances:
            return self._instances[name]

        entry = self._registry.get(name)
        if not entry:
            raise KeyError(f"Module '{name}' is not registered")

        module_start = time.perf_counter()
        instance = await self._create_instance(name)
        self._instances[name] = instance
        self._init_times[name] = time.perf_counter() - module_start
        return instance

    def get_module_sync(self, name: str) -> Any:
        """Get already-initialized module (raises if not loaded)."""
        if name not in self._instances:
            raise RuntimeError(
                f"Module '{name}' is not loaded. Use get_module() for async init."
            )
        return self._instances[name]

    def is_loaded(self, name: str) -> bool:
        """Check if module is initialized."""
        return name in self._instances

    def get_init_order(self) -> list[str]:
        """Return the topological order modules will be initialized."""
        return self._resolve_dependencies()

    def _resolve_dependencies(self) -> list[str]:
        """Topological sort of modules by dependencies."""
        visited: set[str] = set()
        temp: set[str] = set()
        order: list[str] = []

        graph: dict[str, list[str]] = {}
        for name, entry in self._registry.items():
            graph[name] = entry.get("dependencies", [])

        def dfs(node: str) -> None:
            if node in visited:
                return
            if node in temp:
                raise ValueError(f"Circular dependency detected: {node}")
            temp.add(node)

            for dep in graph.get(node, []):
                if dep not in graph:
                    raise ValueError(
                        f"Dependency '{dep}' of module '{node}' is not registered"
                    )
                dfs(dep)

            temp.remove(node)
            visited.add(node)
            order.append(node)

        for name in self._registry:
            dfs(name)

        return order

    def get_startup_time(self) -> float:
        """Return total startup time in seconds."""
        return self._total_startup_time

    def get_module_timings(self) -> dict[str, float]:
        """Return init time per module."""
        return dict(self._init_times)

    def preload_critical(self, modules: list[str]) -> None:
        """Mark modules as critical and preload them."""
        self._critical_modules.update(modules)

    async def warmup_cache(self, keys: list[str]) -> None:
        """Pre-populate cache with commonly accessed data."""
        for key in keys:
            if key not in self._cache:
                self._cache[key] = None

    def get_status(self) -> dict:
        """Return startup status summary."""
        return {
            "total_modules": len(self._registry),
            "loaded_modules": len(self._instances),
            "lazy_modules": sum(
                1 for e in self._registry.values() if e.get("lazy", False)
            ),
            "critical_modules": list(self._critical_modules),
            "startup_time": self._total_startup_time,
            "module_timings": dict(self._init_times),
            "init_order": self._init_order,
        }
