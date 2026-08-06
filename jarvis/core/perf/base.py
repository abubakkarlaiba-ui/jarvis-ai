"""
Performance module — base types and configuration.
===================================================
Shared dataclasses, enums, and settings for performance optimization.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable


class CacheBackend(Enum):
    """Cache storage backends."""
    MEMORY = auto()
    DISK = auto()
    REDIS = auto()


class ProfileMetric(Enum):
    """Types of profiling metrics."""
    CPU_TIME = "cpu_time"
    WALL_TIME = "wall_time"
    MEMORY_PEAK = "memory_peak"
    MEMORY_CURRENT = "memory_current"
    IO_READ = "io_read"
    IO_WRITE = "io_write"
    CALLS = "calls"
    CACHE_HITS = "cache_hits"
    CACHE_MISSES = "cache_misses"


class TaskPriority(Enum):
    """Background task priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    IDLE = 4


class TaskStatus(Enum):
    """Background task status."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    RETRYING = auto()


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()    # Normal operation
    OPEN = auto()      # Failing, reject requests
    HALF_OPEN = auto() # Testing if recovered


class Platform(Enum):
    """Supported platforms."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    UNKNOWN = "unknown"


@dataclass
class CacheEntry:
    """A single cached item."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0
    tags: list[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        return time.time() - self.last_accessed


@dataclass
class CacheConfig:
    """Cache configuration."""
    backend: CacheBackend = CacheBackend.MEMORY
    max_size: int = 1000
    default_ttl: float = 300.0  # 5 minutes
    max_memory_mb: float = 256.0
    eviction_policy: str = "lru"  # lru, lfu, fifo, random
    disk_cache_dir: str = "./data/cache"
    enable_stats: bool = True


@dataclass
class ProfileResult:
    """Result of a profiling session."""
    name: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    cpu_time: float = 0.0
    memory_before: int = 0
    memory_after: int = 0
    memory_peak: int = 0
    calls: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "duration": self.duration,
            "cpu_time": self.cpu_time,
            "memory_before": self.memory_before,
            "memory_after": self.memory_after,
            "memory_peak": self.memory_peak,
            "calls": self.calls,
            "metadata": self.metadata,
        }


@dataclass
class TaskInfo:
    """Information about a background task."""
    id: str = ""
    name: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: float = 0.0
    result: Any = None
    error: str = ""
    retries: int = 0
    max_retries: int = 3
    timeout: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """System health check result."""
    name: str = ""
    status: str = "ok"
    latency_ms: float = 0.0
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""
    uptime: float = 0.0
    requests_total: int = 0
    requests_per_second: float = 0.0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    error_rate: float = 0.0
    cache_hit_rate: float = 0.0
    memory_used_mb: float = 0.0
    memory_available_mb: float = 0.0
    cpu_percent: float = 0.0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    def to_dict(self) -> dict:
        return {
            "uptime": self.uptime,
            "requests_total": self.requests_total,
            "requests_per_second": self.requests_per_second,
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "error_rate": self.error_rate,
            "cache_hit_rate": self.cache_hit_rate,
            "memory_used_mb": self.memory_used_mb,
            "memory_available_mb": self.memory_available_mb,
            "cpu_percent": self.cpu_percent,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
        }


@dataclass
class UpdateInfo:
    """Information about an available update."""
    current_version: str = ""
    latest_version: str = ""
    update_url: str = ""
    release_notes: str = ""
    is_critical: bool = False
    download_size: int = 0
    released_at: datetime | None = None
