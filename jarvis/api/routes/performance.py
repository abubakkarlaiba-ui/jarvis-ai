"""
Performance routes — monitoring, caching, and system health.
===========================================================
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["performance"])


# ── Request / Response models ─────────────────────────────────────


class CacheSetRequest(BaseModel):
    key: str
    value: str | int | float | dict | list
    ttl: float | None = None


class ScheduleRequest(BaseModel):
    name: str
    command: str = ""
    interval: float = 0
    delay: float = 0
    priority: str = "normal"


class CacheResponse(BaseModel):
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    size: int = 0
    evictions: int = 0


class HealthResponse(BaseModel):
    status: str
    uptime: float
    platform: str
    memory: dict
    cache: dict
    tasks: dict
    api_requests: int
    errors: int
    error_rate: float


class MemoryResponse(BaseModel):
    used_mb: float
    total_mb: float
    percent: float
    available_mb: float


class TasksResponse(BaseModel):
    total: int
    running: int
    completed: int
    failed: int


class ProfileResponse(BaseModel):
    operations: dict = {}
    slowest: list = []
    summary: dict = {}


class PlatformResponse(BaseModel):
    system: str
    python_version: str
    cpu_count: int
    total_memory_mb: float
    is_windows: bool
    is_linux: bool
    is_macos: bool


# ── Dependency helper ─────────────────────────────────────────────


def _get_perf():
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    if not hasattr(core, "performance"):
        raise Exception("Performance manager not initialized")
    return core.performance


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Get comprehensive system health."""
    perf = _get_perf()
    return perf.get_health()


@router.get("/health/status")
async def get_health_status():
    """Get quick health status."""
    perf = _get_perf()
    return {"status": perf.get_memory_health().name}


# ── Cache ─────────────────────────────────────────────────────────


@router.get("/cache/stats", response_model=CacheResponse)
async def cache_stats():
    """Get cache statistics."""
    perf = _get_perf()
    return perf.cache_stats()


@router.get("/cache/{key}")
async def cache_get(key: str):
    """Get a cached value."""
    perf = _get_perf()
    value = perf.cache_get(key)
    if value is None:
        return {"found": False}
    return {"found": True, "value": value}


@router.post("/cache")
async def cache_set(request: CacheSetRequest):
    """Set a cached value."""
    perf = _get_perf()
    perf.cache_set(request.key, request.value, ttl=request.ttl)
    return {"success": True}


@router.delete("/cache/{key}")
async def cache_delete(key: str):
    """Delete a cached value."""
    perf = _get_perf()
    result = perf.cache_delete(key)
    return {"success": result}


@router.delete("/cache")
async def cache_clear():
    """Clear all cache entries."""
    perf = _get_perf()
    count = perf.cache_clear()
    return {"cleared": count}


@router.post("/cache/cleanup")
async def cache_cleanup():
    """Clean up expired cache entries."""
    perf = _get_perf()
    count = perf.cache.cleanup_expired()
    return {"cleaned": count}


# ── Memory ────────────────────────────────────────────────────────


@router.get("/memory", response_model=MemoryResponse)
async def get_memory():
    """Get memory usage."""
    perf = _get_perf()
    return perf.get_memory_usage()


@router.get("/memory/health")
async def memory_health():
    """Get memory health status."""
    perf = _get_perf()
    return {"status": perf.get_memory_health().name}


@router.post("/memory/optimize")
async def optimize_memory():
    """Run memory optimization."""
    perf = _get_perf()
    return perf.optimize_memory()


@router.get("/memory/allocations")
async def get_allocations(top_n: int = 20):
    """Get top memory allocations."""
    perf = _get_perf()
    return perf.profiler.get_allocations(top_n)


# ── Tasks ─────────────────────────────────────────────────────────


@router.get("/tasks", response_model=TasksResponse)
async def get_tasks():
    """Get task scheduler stats."""
    perf = _get_perf()
    return perf.scheduler.get_stats()


@router.get("/tasks/list")
async def list_tasks(state: str = None, tag: str = None):
    """List scheduled tasks."""
    perf = _get_perf()
    return perf.list_tasks(state=state, tag=tag)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a task."""
    perf = _get_perf()
    result = await perf.cancel_task(task_id)
    return {"success": result}


# ── Profiling ─────────────────────────────────────────────────────


@router.get("/profile/summary", response_model=ProfileResponse)
async def profile_summary():
    """Get profiling summary."""
    perf = _get_perf()
    return perf.get_profile_summary()


@router.get("/profile/snapshot")
async def profile_snapshot():
    """Take a performance snapshot."""
    perf = _get_perf()
    snapshot = perf.get_snapshot()
    return {
        "timestamp": snapshot.timestamp.isoformat(),
        "cpu_percent": snapshot.cpu_percent,
        "memory_used_mb": snapshot.memory_used_mb,
        "memory_total_mb": snapshot.memory_total_mb,
        "memory_percent": snapshot.memory_percent,
        "active_tasks": snapshot.active_tasks,
        "cache_size": snapshot.cache_size,
        "uptime_seconds": snapshot.uptime_seconds,
    }


@router.get("/profile/top-slowest")
async def top_slowest(count: int = 10):
    """Get slowest operations."""
    perf = _get_perf()
    results = perf.profiler.get_top_slowest(count)
    return [
        {"name": r.name, "avg_time": r.avg_time, "call_count": r.call_count}
        for r in results
    ]


# ── Platform ──────────────────────────────────────────────────────


@router.get("/platform", response_model=PlatformResponse)
async def get_platform():
    """Get platform information."""
    perf = _get_perf()
    info = perf.get_platform()
    return {
        "system": info.system,
        "python_version": info.python_version,
        "cpu_count": perf.cpu.get_cpu_count(),
        "total_memory_mb": perf.platform.get_total_memory() / (1024 * 1024),
        "is_windows": info.is_windows,
        "is_linux": info.is_linux,
        "is_macos": info.is_macos,
    }


# ── Updates ───────────────────────────────────────────────────────


@router.get("/updates/check")
async def check_updates():
    """Check for available updates."""
    perf = _get_perf()
    return await perf.check_updates()


# ── Report ────────────────────────────────────────────────────────


@router.get("/report")
async def get_report():
    """Get full performance report."""
    perf = _get_perf()
    return {"report": perf.get_performance_report()}
