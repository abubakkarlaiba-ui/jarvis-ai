"""
Performance module — memory management, GC optimization, leak detection.
========================================================================
Monitors memory usage, performs garbage collection, and detects leaks.
"""

from __future__ import annotations

import asyncio
import gc
import sys
import threading
import time
from typing import Any, Callable

try:
    import psutil
except ImportError:
    psutil = None

try:
    import objgraph
except ImportError:
    objgraph = None

from jarvis.core.perf.base import ProfileMetric


class MemoryManager:
    """Memory management, GC optimization, leak detection."""

    def __init__(self, check_interval: float = 30.0) -> None:
        self._check_interval = check_interval
        self._monitoring = False
        self._monitor_task: asyncio.Task | None = None
        self._history: list[dict[str, Any]] = []
        self._memory_limit_mb: float | None = None
        self._cleanup_registry: dict[str, Callable] = {}
        self._high_memory_callbacks: list[dict[str, Any]] = []
        self._snapshots: list[dict[str, Any]] = []
        self._module_sizes: dict[str, int] = {}
        self._lock = threading.Lock()

    def get_memory_usage(self) -> dict[str, Any]:
        """Get current memory usage (RSS, VMS, percent, available)."""
        if psutil is None:
            return {
                "rss": 0,
                "vms": 0,
                "percent": 0.0,
                "available": 0,
                "error": "psutil not installed",
            }

        process = psutil.Process()
        mem = process.memory_info()
        virtual = psutil.virtual_memory()

        return {
            "rss": mem.rss,
            "vms": mem.vms,
            "percent": virtual.percent,
            "available": virtual.available,
            "rss_mb": mem.rss / (1024 * 1024),
            "vms_mb": mem.vms / (1024 * 1024),
        }

    def get_memory_stats(self) -> dict[str, Any]:
        """Detailed memory stats (by module, total, peak)."""
        usage = self.get_memory_usage()
        return {
            "current": usage,
            "by_module": self.get_by_module(),
            "history_count": len(self._history),
            "memory_limit_mb": self._memory_limit_mb,
            "cleanup_handlers": len(self._cleanup_registry),
            "gc_stats": {
                "collections": gc.get_count(),
                "thresholds": gc.get_threshold(),
                "garbage_count": len(gc.garbage),
            },
        }

    def optimize(self) -> dict[str, int]:
        """Run optimization (gc.collect, clear caches, release freed memory)."""
        freed = self.force_gc()

        for name, func in self._cleanup_registry.items():
            try:
                func()
            except Exception:
                pass

        return {"freed_bytes": freed}

    def force_gc(self) -> int:
        """Force garbage collection and return freed bytes."""
        before = self.get_memory_usage().get("rss", 0)

        gc.collect(2)

        after = self.get_memory_usage().get("rss", 0)
        freed = max(0, before - after)
        return freed

    def set_memory_limit(self, limit_mb: float) -> None:
        """Set soft memory limit."""
        self._memory_limit_mb = limit_mb

    def check_memory_limit(self) -> bool:
        """Check if memory limit is exceeded."""
        if self._memory_limit_mb is None:
            return False

        usage = self.get_memory_usage()
        current_mb = usage.get("rss_mb", 0)
        return current_mb > self._memory_limit_mb

    def get_leak_candidates(
        self, threshold_mb: float = 10.0
    ) -> list[dict[str, Any]]:
        """Detect objects growing in size."""
        candidates: list[dict[str, Any]] = []

        if objgraph is not None:
            try:
                growth = objgraph.get_growth(limit=10)
                for item in growth:
                    if isinstance(item, dict):
                        count = item.get("count", 0)
                        delta = item.get("delta", 0)
                        name = item.get("name", "unknown")
                        if delta > 0:
                            candidates.append({
                                "type": name,
                                "count": count,
                                "delta": delta,
                                "source": "objgraph",
                            })
            except Exception:
                pass

        if len(self._snapshots) >= 2:
            old = self._snapshots[-2]
            new = self._snapshots[-1]
            diff = self._compare_snapshots(old, new)
            for name, delta in diff.items():
                delta_mb = delta / (1024 * 1024)
                if delta_mb > threshold_mb:
                    candidates.append({
                        "type": name,
                        "delta_bytes": delta,
                        "delta_mb": round(delta_mb, 2),
                        "source": "snapshot_diff",
                    })

        return candidates

    def start_monitoring(self, interval: float | None = None) -> None:
        """Start periodic memory monitoring."""
        if self._monitoring:
            return

        self._monitoring = True
        self._check_interval = interval or self._check_interval

    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._monitoring = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

    def get_history(self, count: int = 100) -> list[dict[str, Any]]:
        """Get memory usage history."""
        return list(self._history[-count:])

    def get_by_module(self) -> dict[str, int]:
        """Estimate memory usage by module."""
        result: dict[str, int] = {}

        for mod_name, mod_obj in sorted(sys.modules.items()):
            try:
                size = sys.getsizeof(mod_obj)
                result[mod_name] = size
            except Exception:
                pass

        return result

    def _take_snapshot(self) -> dict[str, Any]:
        """Take a memory snapshot."""
        usage = self.get_memory_usage()
        snapshot = {
            "timestamp": time.time(),
            "rss": usage.get("rss", 0),
            "vms": usage.get("vms", 0),
            "percent": usage.get("percent", 0.0),
            "objects": self._count_objects(),
        }
        with self._lock:
            self._snapshots.append(snapshot)
            if len(self._snapshots) > 100:
                self._snapshots = self._snapshots[-100:]
        return snapshot

    def _count_objects(self) -> dict[str, int]:
        """Count objects by type."""
        counts: dict[str, int] = {}
        for obj in gc.get_objects():
            type_name = type(obj).__name__
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts

    def _compare_snapshots(
        self, old: dict[str, Any], new: dict[str, Any]
    ) -> dict[str, int]:
        """Compare two snapshots and return differences."""
        old_objs = old.get("objects", {})
        new_objs = new.get("objects", {})
        diff: dict[str, int] = {}

        all_types = set(old_objs.keys()) | set(new_objs.keys())
        for type_name in all_types:
            delta = new_objs.get(type_name, 0) - old_objs.get(type_name, 0)
            if delta != 0:
                diff[type_name] = delta

        return diff

    def register_cleanup(self, name: str, func: Callable) -> None:
        """Register a cleanup function to call on memory pressure."""
        self._cleanup_registry[name] = func

    def on_high_memory(
        self,
        threshold_percent: float = 85.0,
        callback: Callable | None = None,
    ) -> None:
        """Register callback for high memory."""
        self._high_memory_callbacks.append({
            "threshold": threshold_percent,
            "callback": callback,
        })

    def get_recommendations(self) -> list[str]:
        """Get memory optimization recommendations."""
        recommendations: list[str] = []
        usage = self.get_memory_usage()
        percent = usage.get("percent", 0)
        rss_mb = usage.get("rss_mb", 0)

        if percent > 80:
            recommendations.append(
                f"Memory usage at {percent:.1f}%. Consider reducing cache sizes."
            )

        if rss_mb > 500:
            recommendations.append(
                f"RSS at {rss_mb:.1f}MB. Review large data structures."
            )

        gc_count = gc.get_count()
        if gc_count[0] > 100:
            recommendations.append(
                "High gen0 GC count. Consider tuning GC thresholds."
            )

        if len(gc.garbage) > 0:
            recommendations.append(
                f"{len(gc.garbage)} uncollectable objects. Check for circular references."
            )

        if not recommendations:
            recommendations.append("Memory usage is within normal parameters.")

        return recommendations
