"""
Performance module — base types and configuration.
==================================================
Shared dataclasses, enums, and settings for performance optimization.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable


class CacheStrategy(Enum):
    """Cache eviction strategies."""
    LRU = auto()      # Least Recently Used
    LFU = auto()      # Least Frequently Used
    TTL = auto()      # Time To Live
    FIFO = auto()     # First In First Out


class TaskPriority(Enum):
    """Background task priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    IDLE = 4


class TaskState(Enum):
    """Background task states."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    RETRYING = auto()


class ProfileMetric(Enum):
    """Metrics collected by the profiler."""
    EXECUTION_TIME = "execution_time"
    MEMORY_USAGE = "memory_usage"
    CPU_PERCENT = "cpu_percent"
    CALL_COUNT = "call_count"
    ERROR_COUNT = "error_count"
    CACHE_HITS = "cache_hits"
    CACHE_MISSES = "cache_misses"


class HealthStatus(Enum):
    """System health status."""
    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()
    CRITICAL = auto()


@dataclass
class CacheEntry:
    """A single cached item."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: float = 0.0  # 0 = no expiry
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return (time.time() - self.created_at) > self.ttl


@dataclass
class ScheduledTask:
    """A background scheduled task."""
    id: str = ""
    name: str = ""
    func: Callable | None = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    state: TaskState = TaskState.PENDING
    interval: float = 0.0  # seconds, 0 = one-shot
    delay: float = 0.0     # initial delay before first run
    created_at: float = field(default_factory=time.time)
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    error_count: int = 0
    last_error: str = ""
    max_retries: int = 3
    timeout: float = 300.0
    tags: list[str] = field(default_factory=list)


@dataclass
class ProfileResult:
    """Result of profiling a function or operation."""
    name: str = ""
    execution_time: float = 0.0
    memory_before: int = 0
    memory_after: int = 0
    memory_delta: int = 0
    cpu_percent: float = 0.0
    call_count: int = 1
    error_count: int = 0
    min_time: float = float("inf")
    max_time: float = 0.0
    avg_time: float = 0.0
    timestamps: list[float] = field(default_factory=list)


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance metrics."""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    memory_percent: float = 0.0
    disk_used_percent: float = 0.0
    active_tasks: int = 0
    cache_size: int = 0
    cache_hit_rate: float = 0.0
    uptime_seconds: float = 0.0
    api_requests: int = 0
    error_rate: float = 0.0


@dataclass
class PlatformInfo:
    """Cross-platform compatibility info."""
    system: str = ""       # windows, linux, darwin
    release: str = ""
    version: str = ""
    machine: str = ""
    python_version: str = ""
    is_windows: bool = False
    is_linux: bool = False
    is_macos: bool = False
    shell: str = ""
    path_separator: str = ""
    temp_dir: str = ""
    home_dir: str = ""
