"""
Performance Manager — orchestrator for all performance submodules.
================================================================
Coordinates caching, scheduling, profiling, memory, and startup.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from jarvis.core.performance.base import (
    CacheStrategy,
    HealthStatus,
    PerformanceSnapshot,
    PlatformInfo,
    ProfileResult,
    TaskPriority,
    TaskState,
)
from jarvis.core.performance.cache import Cache
from jarvis.core.performance.cpu_optimizer import CPUOptimizer
from jarvis.core.performance.error_recovery import ErrorRecovery
from jarvis.core.performance.lazy_loader import LazyLoader
from jarvis.core.performance.memory_manager import MemoryManager
from jarvis.core.performance.platform_compat import PlatformCompat
from jarvis.core.performance.profiler import Profiler
from jarvis.core.performance.scheduler import TaskScheduler
from jarvis.core.performance.startup import StartupManager
from jarvis.core.performance.updater import AutoUpdater

logger = logging.getLogger(__name__)


class PerformanceManager:
    """Unified performance orchestrator.

    Coordinates caching, scheduling, profiling, memory management,
    startup optimization, and error recovery.
    """

    def __init__(self, data_dir: str = "./data/performance"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize sub-modules
        self.platform = PlatformCompat()
        self.lazy_loader = LazyLoader()
        self.cache = Cache(max_size=5000, default_ttl=300.0, strategy=CacheStrategy.LRU)
        self.scheduler = TaskScheduler(max_workers=4)
        self.memory = MemoryManager(warning_threshold=80.0, critical_threshold=95.0)
        self.profiler = Profiler(data_dir=str(self.data_dir))
        self.startup = StartupManager()
        self.error_recovery = ErrorRecovery()
        self.updater = AutoUpdater(current_version="2.0.0")
        self.cpu = CPUOptimizer()

        self._start_time = time.time()
        self._api_requests = 0
        self._errors = 0

        logger.info(
            "PerformanceManager initialized on %s",
            self.platform.get_platform(),
        )

    # ── Startup ───────────────────────────────────────────────────

    async def initialize(self) -> dict:
        """Initialize all performance sub-systems."""
        logger.info("Initializing performance sub-systems...")
        results = {}

        # Start memory monitoring
        self.memory.start_monitoring(interval=10.0)
        results["memory_monitoring"] = True

        # Start scheduler
        await self.scheduler.start()
        results["scheduler"] = True

        # Schedule periodic tasks
        self.scheduler.schedule(
            name="cache_cleanup",
            func=self.cache.cleanup_expired,
            interval=60.0,
            priority=TaskPriority.LOW,
            tags=["maintenance"],
        )
        self.scheduler.schedule(
            name="memory_check",
            func=self._check_memory_health,
            interval=30.0,
            priority=TaskPriority.LOW,
            tags=["monitoring"],
        )
        results["periodic_tasks"] = True

        # Enable tracemalloc
        try:
            self.profiler.enable_tracemalloc()
            results["tracemalloc"] = True
        except Exception:
            results["tracemalloc"] = False

        logger.info("Performance sub-systems initialized: %s", results)
        return results

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down performance manager...")
        await self.scheduler.stop()
        self.memory.stop_monitoring()
        logger.info("Performance manager shut down")

    # ── Cache facade ──────────────────────────────────────────────

    def cache_get(self, key: str) -> Any:
        return self.cache.get(key)

    def cache_set(self, key: str, value: Any, ttl: float = None) -> None:
        self.cache.set(key, value, ttl=ttl)

    def cache_delete(self, key: str) -> bool:
        return self.cache.delete(key)

    def cache_clear(self) -> int:
        return self.cache.clear()

    def cache_stats(self) -> dict:
        return self.cache.get_stats()

    # ── Scheduler facade ──────────────────────────────────────────

    async def schedule_task(
        self,
        name: str,
        func: Callable,
        **kwargs,
    ) -> str:
        return await self.scheduler.schedule(name, func, **kwargs)

    async def cancel_task(self, task_id: str) -> bool:
        return self.scheduler.cancel(task_id)

    def list_tasks(self, **kwargs) -> list[dict]:
        return self.scheduler.list_tasks(**kwargs)

    # ── Profiler facade ───────────────────────────────────────────

    def profile_start(self, name: str) -> None:
        self.profiler.start(name)

    def profile_stop(self, name: str) -> ProfileResult:
        return self.profiler.stop(name)

    def get_profile_summary(self) -> dict:
        return self.profiler.get_summary()

    def get_snapshot(self) -> PerformanceSnapshot:
        return self.profiler.get_snapshot()

    # ── Memory facade ─────────────────────────────────────────────

    def get_memory_usage(self) -> dict:
        return self.memory.get_usage()

    def get_memory_health(self) -> HealthStatus:
        return self.memory.check_health()

    def optimize_memory(self) -> dict:
        return self.memory.optimize()

    # ── Error recovery facade ─────────────────────────────────────

    def create_circuit_breaker(self, name: str, **kwargs) -> None:
        self.error_recovery.create_circuit_breaker(name, **kwargs)

    async def safe_call(self, name: str, coro) -> Any:
        return await self.error_recovery.async_call(name, coro)

    # ── Lazy loading facade ───────────────────────────────────────

    def lazy_load(self, module_path: str) -> Any:
        return self.lazy_loader.load(module_path)

    def lazy_register(self, module_path: str) -> None:
        self.lazy_loader.register(module_path)

    # ── Platform facade ───────────────────────────────────────────

    def get_platform(self) -> PlatformInfo:
        return self.platform.detect()

    # ── Update facade ─────────────────────────────────────────────

    async def check_updates(self) -> dict:
        return await self.updater.check_for_updates()

    # ── Tracking ──────────────────────────────────────────────────

    def record_request(self) -> None:
        self._api_requests += 1

    def record_error(self) -> None:
        self._errors += 1

    # ── System health ─────────────────────────────────────────────

    def get_health(self) -> dict:
        """Get comprehensive system health status."""
        mem = self.memory.get_usage()
        mem_health = self.memory.check_health()

        status = HealthStatus.HEALTHY
        if mem_health == HealthStatus.CRITICAL:
            status = HealthStatus.CRITICAL
        elif mem_health == HealthStatus.UNHEALTHY:
            status = HealthStatus.UNHEALTHY
        elif mem_health == HealthStatus.DEGRADED:
            status = HealthStatus.DEGRADED

        return {
            "status": status.name,
            "uptime": time.time() - self._start_time,
            "platform": self.platform.get_platform(),
            "memory": mem,
            "cache": self.cache.get_stats(),
            "tasks": self.scheduler.get_stats(),
            "profiler": self.profiler.get_summary(),
            "api_requests": self._api_requests,
            "errors": self._errors,
            "error_rate": (
                self._errors / self._api_requests
                if self._api_requests > 0 else 0
            ),
            "circuit_breakers": self.error_recovery.get_all_states(),
            "lazy_modules": {
                "registered": len(self.lazy_loader.get_loaded()),
                "loaded": self.lazy_loader.get_loaded(),
            },
        }

    def get_performance_report(self) -> str:
        """Generate a human-readable performance report."""
        health = self.get_health()
        lines = [
            "=" * 50,
            "JARVIS PERFORMANCE REPORT",
            "=" * 50,
            f"Status:      {health['status']}",
            f"Uptime:      {health['uptime']:.0f}s ({health['uptime']/3600:.1f}h)",
            f"Platform:    {health['platform']}",
            f"API Requests:{health['api_requests']}",
            f"Error Rate:  {health['error_rate']:.2%}",
            "",
            "--- Memory ---",
            f"Used:        {health['memory'].get('used_mb', 0):.1f} MB",
            f"Total:       {health['memory'].get('total_mb', 0):.1f} MB",
            f"Percent:     {health['memory'].get('percent', 0):.1f}%",
            "",
            "--- Cache ---",
            f"Size:        {health['cache'].get('size', 0)}",
            f"Hit Rate:    {health['cache'].get('hit_rate', 0):.1%}",
            f"Hits:        {health['cache'].get('hits', 0)}",
            f"Misses:      {health['cache'].get('misses', 0)}",
            "",
            "--- Tasks ---",
            f"Total:       {health['tasks'].get('total', 0)}",
            f"Running:     {health['tasks'].get('running', 0)}",
            f"Completed:   {health['tasks'].get('completed', 0)}",
            f"Failed:      {health['tasks'].get('failed', 0)}",
            "",
            "--- Circuit Breakers ---",
        ]
        for name, state in health.get("circuit_breakers", {}).items():
            lines.append(f"  {name}: {state}")

        lines.append("=" * 50)
        return "\n".join(lines)

    # ── Internal helpers ──────────────────────────────────────────

    async def _check_memory_health(self) -> None:
        """Periodic memory health check."""
        status = self.memory.check_health()
        if status in (HealthStatus.CRITICAL, HealthStatus.UNHEALTHY):
            logger.warning("Memory health: %s", status.name)
            self.memory.optimize()
