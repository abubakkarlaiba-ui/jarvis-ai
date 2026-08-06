from jarvis.core.performance.base import HealthStatus
import psutil
import tracemalloc
import gc
import os
import time
from typing import Callable


class MemoryManager:
    def __init__(self, warning_threshold: float = 80.0, critical_threshold: float = 95.0):
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._memory_limit_mb: float | None = None
        self._cache_cleaners: list[Callable[[], int]] = []
        self._history: list[dict] = []
        self._monitoring = False
        self._monitor_task = None
        self._threshold_callbacks: list[Callable] = []
        self._last_warning = 0
        self._last_critical = 0

    def get_usage(self) -> dict:
        mem = psutil.virtual_memory()
        return {
            "used": mem.used,
            "total": mem.total,
            "percent": mem.percent,
            "available": mem.available,
        }

    def get_detailed_usage(self) -> dict:
        usage = self.get_usage()
        try:
            snap = tracemalloc.take_snapshot()
            stats = snap.statistics("lineno")
            python_alloc = sum(s.size for s in stats[:50])
        except Exception:
            python_alloc = 0
        mem = psutil.virtual_memory()
        return {
            **usage,
            "python_objects": python_alloc,
            "buffers": getattr(mem, "buffers", 0),
            "cached": getattr(mem, "cached", 0),
        }

    def check_health(self) -> HealthStatus:
        usage = self.get_usage()
        percent = usage["percent"]
        if percent >= self._critical_threshold:
            return HealthStatus.CRITICAL
        elif percent >= self._warning_threshold:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY

    def cleanup(self, force: bool = False) -> dict:
        actions = []
        freed = 0
        freed += self._cleanup_caches()
        actions.append("caches")
        freed += self._cleanup_temp_files()
        actions.append("temp_files")
        if force:
            freed += self._gc_collect()
            actions.append("gc")
        return {"freed_bytes": freed, "actions": actions}

    def _cleanup_caches(self) -> int:
        total = 0
        for cleaner in self._cache_cleaners:
            try:
                total += cleaner()
            except Exception:
                pass
        return total

    def _cleanup_temp_files(self) -> int:
        freed = 0
        temp_dirs = [os.environ.get("TEMP", ""), os.environ.get("TMP", "")]
        cutoff = time.time() - 86400
        for temp_dir in temp_dirs:
            if not temp_dir or not os.path.isdir(temp_dir):
                continue
            for entry in os.scandir(temp_dir):
                try:
                    if entry.is_file() and entry.stat().st_mtime < cutoff:
                        size = entry.stat().st_size
                        os.unlink(entry.path)
                        freed += size
                except Exception:
                    pass
        return freed

    def _gc_collect(self) -> int:
        before = len(gc.get_objects())
        collected = gc.collect()
        after = len(gc.get_objects())
        return before - after

    def set_memory_limit(self, limit_mb: float) -> None:
        self._memory_limit_mb = limit_mb

    def is_over_limit(self) -> bool:
        if self._memory_limit_mb is None:
            return False
        usage = self.get_usage()
        used_mb = usage["used"] / (1024 * 1024)
        return used_mb > self._memory_limit_mb

    def get_top_allocations(self, count: int = 10) -> list[dict]:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        snap = tracemalloc.take_snapshot()
        stats = snap.statistics("lineno")
        results = []
        for stat in stats[:count]:
            results.append({
                "file": stat.traceback.format()[0],
                "size": stat.size,
                "count": stat.count,
            })
        return results

    def start_monitoring(self, interval: float = 5.0) -> None:
        self._monitoring = True
        self._monitor_interval = interval

    def stop_monitoring(self) -> None:
        self._monitoring = False

    def on_threshold(self, callback: Callable) -> None:
        self._threshold_callbacks.append(callback)

    def _check_thresholds(self) -> None:
        usage = self.get_usage()
        percent = usage["percent"]
        now = time.time()
        if percent >= self._critical_threshold and now - self._last_critical > 60:
            self._last_critical = now
            for cb in self._threshold_callbacks:
                try:
                    cb("critical", usage)
                except Exception:
                    pass
        elif percent >= self._warning_threshold and now - self._last_warning > 60:
            self._last_warning = now
            for cb in self._threshold_callbacks:
                try:
                    cb("warning", usage)
                except Exception:
                    pass

    def get_history(self, count: int = 100) -> list[dict]:
        return self._history[-count:]

    def optimize(self) -> dict:
        results = {}
        gc_freed = self._gc_collect()
        results["gc_freed"] = gc_freed
        cache_freed = self._cleanup_caches()
        results["cache_freed"] = cache_freed
        temp_freed = self._cleanup_temp_files()
        results["temp_freed"] = temp_freed
        results["total_freed"] = gc_freed + cache_freed + temp_freed
        self._history.append({
            "timestamp": time.time(),
            "usage": self.get_usage(),
            "result": results,
        })
        return results
