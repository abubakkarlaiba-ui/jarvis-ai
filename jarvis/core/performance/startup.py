"""
Performance module — fast startup orchestrator with deferred loading.
====================================================================
Manages startup phases, dependency ordering, and deferred task execution.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable

from jarvis.core.performance.base import PerformanceSnapshot, ProfileResult


class StartupManager:
    """Orchestrates application startup with dependency-ordered phases."""

    def __init__(self) -> None:
        self._phases: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._deferred_tasks: list[str] = []
        self._cleanup_funcs: list[Callable] = []
        self._phase_times: dict[str, float] = {}
        self._total_startup_time: float = 0.0
        self._phase_ready: dict[str, asyncio.Event] = {}
        self._phase_results: dict[str, dict[str, Any]] = {}
        self._start_time: float = 0.0

    def register_phase(
        self, name: str, dependencies: list[str] | None = None, priority: int = 0
    ) -> None:
        """Register a startup phase with optional dependencies."""
        if dependencies is None:
            dependencies = []
        self._phases[name] = {
            "dependencies": dependencies,
            "priority": priority,
        }
        self._phase_ready[name] = asyncio.Event()

    def register_task(
        self,
        phase: str,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> None:
        """Register a task within a phase."""
        if phase not in self._phases:
            raise ValueError(f"Phase '{phase}' not registered")
        if kwargs is None:
            kwargs = {}
        self._tasks[phase].append(
            {"name": name, "func": func, "args": args, "kwargs": kwargs}
        )

    async def run_startup(self) -> dict:
        """Execute all phases in dependency order and return timing results."""
        self._start_time = time.perf_counter()
        ordered = self._topological_sort(self._phases)
        results: dict[str, Any] = {}

        for phase_name in ordered:
            results[phase_name] = await self.run_phase(phase_name)

        self._total_startup_time = time.perf_counter() - self._start_time
        results["__total__"] = self._total_startup_time
        return results

    async def run_phase(self, phase_name: str) -> dict:
        """Run a single phase and return its timing."""
        if phase_name not in self._phases:
            raise ValueError(f"Phase '{phase_name}' not registered")

        phase = self._phases[phase_name]
        for dep in phase["dependencies"]:
            if dep not in self._phase_ready:
                raise RuntimeError(
                    f"Dependency '{dep}' for phase '{phase_name}' not found"
                )
            await asyncio.wait_for(self._phase_ready[dep].wait(), timeout=30)

        phase_start = time.perf_counter()
        task_times: dict[str, float] = {}

        for task in self._tasks.get(phase_name, []):
            _, elapsed = self._measure_time(
                task["func"], *task["args"], **task["kwargs"]
            )
            task_times[task["name"]] = elapsed

        phase_elapsed = time.perf_counter() - phase_start
        self._phase_times[phase_name] = phase_elapsed
        self._phase_ready[phase_name].set()

        result = {"time": phase_elapsed, "tasks": task_times}
        self._phase_results[phase_name] = result
        return result

    def _topological_sort(self, phases: dict) -> list[str]:
        """Sort phases by their dependency graph."""
        visited: set[str] = set()
        order: list[str] = []

        def dfs(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            for dep in phases[name]["dependencies"]:
                dfs(dep)
            order.append(name)

        for phase_name in phases:
            dfs(phase_name)
        return order

    def get_startup_time(self) -> float:
        """Get total startup time in seconds."""
        return self._total_startup_time

    def get_phase_times(self) -> dict[str, float]:
        """Get per-phase timing in seconds."""
        return dict(self._phase_times)

    def get_deferred_tasks(self) -> list[str]:
        """List tasks that can be deferred to background."""
        return list(self._deferred_tasks)

    async def run_deferred(self) -> None:
        """Run deferred tasks in the background."""
        for task_name in self._deferred_tasks:
            for phase_tasks in self._tasks.values():
                for task in phase_tasks:
                    if task["name"] == task_name:
                        asyncio.create_task(
                            asyncio.to_thread(
                                task["func"], *task["args"], **task["kwargs"]
                            )
                        )

    def register_cleanup(self, func: Callable) -> None:
        """Register a cleanup function for shutdown."""
        self._cleanup_funcs.append(func)

    async def run_cleanup(self) -> None:
        """Run all registered cleanup functions."""
        for func in self._cleanup_funcs:
            try:
                result = func()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    def get_readiness(self) -> dict:
        """Check which phases are ready."""
        return {
            name: event.is_set()
            for name, event in self._phase_ready.items()
        }

    async def wait_for_ready(self, phase: str, timeout: float = 30) -> bool:
        """Wait for a specific phase to complete."""
        if phase not in self._phase_ready:
            return False
        try:
            await asyncio.wait_for(self._phase_ready[phase].wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def _measure_time(self, func: Callable, *args: Any, **kwargs: Any) -> tuple[Any, float]:
        """Measure execution time of a callable."""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        return result, elapsed
