"""
JARVIS Performance module.
=========================
Performance optimization, caching, scheduling, and monitoring.

Quick Start:
    from jarvis.core.performance import PerformanceManager

    perf = PerformanceManager()
    await perf.initialize()
    perf.cache_set("key", "value")
"""

from jarvis.core.performance.base import (
    CacheStrategy,
    CacheEntry,
    HealthStatus,
    PerformanceSnapshot,
    PlatformInfo,
    ProfileMetric,
    ProfileResult,
    ScheduledTask,
    TaskPriority,
    TaskState,
)
from jarvis.core.performance.cache import Cache
from jarvis.core.performance.cpu_optimizer import CPUOptimizer
from jarvis.core.performance.error_recovery import ErrorRecovery
from jarvis.core.performance.lazy_loader import LazyLoader
from jarvis.core.performance.memory_manager import MemoryManager
from jarvis.core.performance.performance_manager import PerformanceManager
from jarvis.core.performance.platform_compat import PlatformCompat
from jarvis.core.performance.profiler import Profiler
from jarvis.core.performance.scheduler import TaskScheduler
from jarvis.core.performance.startup import StartupManager
from jarvis.core.performance.updater import AutoUpdater

__all__ = [
    "Cache",
    "CacheEntry",
    "CacheStrategy",
    "CPUOptimizer",
    "ErrorRecovery",
    "HealthStatus",
    "LazyLoader",
    "MemoryManager",
    "PerformanceManager",
    "PerformanceSnapshot",
    "PlatformCompat",
    "PlatformInfo",
    "ProfileMetric",
    "ProfileResult",
    "Profiler",
    "ScheduledTask",
    "Scheduler",
    "StartupManager",
    "TaskPriority",
    "TaskState",
    "AutoUpdater",
]
