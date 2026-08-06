"""
Performance module — profiling and metrics collection.
======================================================
High-resolution timing, memory tracking, and CPU monitoring.
"""

from __future__ import annotations

import asyncio
import json
import time
import tracemalloc
from collections import defaultdict
from typing import Any, Callable

import psutil

from jarvis.core.performance.base import PerformanceSnapshot, ProfileResult


class Profiler:
    """Profiles operations and collects performance metrics."""

    def __init__(self, data_dir: str = "./data/performance") -> None:
        self._data_dir = data_dir
        self._active_timers: dict[str, float] = {}
        self._results: dict[str, ProfileResult] = {}
        self._custom_metrics: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._tracemalloc_enabled = False

    def start(self, name: str) -> None:
        """Start timing a named operation."""
        self._active_timers[name] = time.perf_counter()

    def stop(self, name: str) -> ProfileResult:
        """Stop timing and record the result."""
        if name not in self._active_timers:
            raise ValueError(f"No active timer named '{name}'")
        elapsed = time.perf_counter() - self._active_timers.pop(name)
        memory_after = self._capture_memory()
        cpu = self._capture_cpu()

        if name in self._results:
            result = self._results[name]
            result.execution_time += elapsed
            result.call_count += 1
            result.memory_after = memory_after
            result.memory_delta = memory_after - result.memory_before
            result.cpu_percent = cpu
            result.min_time = min(result.min_time, elapsed)
            result.max_time = max(result.max_time, elapsed)
            result.avg_time = result.execution_time / result.call_count
            result.timestamps.append(time.time())
        else:
            memory_before = memory_after
            self._results[name] = ProfileResult(
                name=name,
                execution_time=elapsed,
                memory_before=memory_before,
                memory_after=memory_after,
                memory_delta=0,
                cpu_percent=cpu,
                call_count=1,
                min_time=elapsed,
                max_time=elapsed,
                avg_time=elapsed,
                timestamps=[time.time()],
            )
        return self._results[name]

    async def async_profile(self, name: str, coro: Any) -> ProfileResult:
        """Profile an async coroutine."""
        self.start(name)
        try:
            result = await coro
            self.stop(name)
        except Exception:
            self.stop(name)
            raise
        return self._results[name]

    def decorator(self, name: str | None = None) -> Callable:
        """Create a profiling decorator for a function."""
        def wrapper(func: Callable) -> Callable:
            op_name = name or func.__name__

            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                self.start(op_name)
                try:
                    result = func(*args, **kwargs)
                    self.stop(op_name)
                    return result
                except Exception:
                    self.stop(op_name)
                    raise

            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                self.start(op_name)
                try:
                    result = await func(*args, **kwargs)
                    self.stop(op_name)
                    return result
                except Exception:
                    self.stop(op_name)
                    raise

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return wrapper

    def record_metric(self, name: str, value: float, tags: dict | None = None) -> None:
        """Record a custom metric value."""
        if tags is None:
            tags = {}
        self._custom_metrics[name].append(
            {"value": value, "tags": tags, "timestamp": time.time()}
        )

    def get_result(self, name: str) -> ProfileResult | None:
        """Get a specific profile result."""
        return self._results.get(name)

    def get_all_results(self) -> dict[str, ProfileResult]:
        """Get all profile results."""
        return dict(self._results)

    def get_top_slowest(self, count: int = 10) -> list[ProfileResult]:
        """Get the slowest operations by total execution time."""
        sorted_results = sorted(
            self._results.values(),
            key=lambda r: r.execution_time,
            reverse=True,
        )
        return sorted_results[:count]

    def get_top_memory(self, count: int = 10) -> list[ProfileResult]:
        """Get the most memory-intensive operations."""
        sorted_results = sorted(
            self._results.values(),
            key=lambda r: abs(r.memory_delta),
            reverse=True,
        )
        return sorted_results[:count]

    def get_summary(self) -> dict:
        """Get an overall profiling summary."""
        if not self._results:
            return {"total_operations": 0, "total_time": 0.0}

        total_time = sum(r.execution_time for r in self._results.values())
        total_calls = sum(r.call_count for r in self._results.values())
        total_errors = sum(r.error_count for r in self._results.values())
        peak_memory = max(
            (r.memory_after for r in self._results.values()), default=0
        )

        return {
            "total_operations": len(self._results),
            "total_calls": total_calls,
            "total_time": total_time,
            "total_errors": total_errors,
            "peak_memory_bytes": peak_memory,
            "average_time": total_time / total_calls if total_calls else 0.0,
            "slowest": self.get_top_slowest(1)[0].name if self._results else "",
        }

    def export_results(self, format: str = "json") -> str:
        """Export all results in the specified format."""
        if format == "json":
            data = {}
            for name, result in self._results.items():
                data[name] = {
                    "name": result.name,
                    "execution_time": result.execution_time,
                    "memory_before": result.memory_before,
                    "memory_after": result.memory_after,
                    "memory_delta": result.memory_delta,
                    "cpu_percent": result.cpu_percent,
                    "call_count": result.call_count,
                    "error_count": result.error_count,
                    "min_time": result.min_time,
                    "max_time": result.max_time,
                    "avg_time": result.avg_time,
                }
            return json.dumps(data, indent=2)
        raise ValueError(f"Unsupported export format: {format}")

    def clear(self) -> None:
        """Clear all recorded results and timers."""
        self._active_timers.clear()
        self._results.clear()
        self._custom_metrics.clear()

    def _capture_memory(self) -> int:
        """Get current memory usage in bytes."""
        try:
            process = psutil.Process()
            return process.memory_info().rss
        except Exception:
            return 0

    def _capture_cpu(self) -> float:
        """Get current CPU percent."""
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return 0.0

    def get_snapshot(self) -> PerformanceSnapshot:
        """Take a full performance snapshot."""
        try:
            vm = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            process = psutil.Process()

            return PerformanceSnapshot(
                cpu_percent=psutil.cpu_percent(interval=None),
                memory_used_mb=vm.used / (1024 * 1024),
                memory_total_mb=vm.total / (1024 * 1024),
                memory_percent=vm.percent,
                disk_used_percent=disk.percent,
            )
        except Exception:
            return PerformanceSnapshot()

    def enable_tracemalloc(self) -> None:
        """Enable tracemalloc for memory allocation tracking."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        self._tracemalloc_enabled = True

    def get_allocations(self, top_n: int = 20) -> list[dict]:
        """Get top memory allocations by size."""
        if not self._tracemalloc_enabled or not tracemalloc.is_tracing():
            return []

        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")[:top_n]

        allocations = []
        for stat in top_stats:
            allocations.append(
                {
                    "file": stat.traceback.format()[-1] if stat.traceback else "",
                    "size_bytes": stat.size,
                    "count": stat.count,
                }
            )
        return allocations
