"""
CPU Optimizer — CPU profiling and optimization.
===============================================
Provides CPU monitoring, thread pool management, and optimization.
"""

from __future__ import annotations

import logging
import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CPUOptimizer:
    """CPU monitoring and optimization utilities."""

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(4, multiprocessing.cpu_count())
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._usage_history: list[float] = []
        self._max_history = 100

    def get_cpu_count(self) -> int:
        return multiprocessing.cpu_count()

    def get_cpu_usage(self) -> float:
        try:
            import psutil
            usage = psutil.cpu_percent(interval=0.1)
            self._usage_history.append(usage)
            if len(self._usage_history) > self._max_history:
                self._usage_history.pop(0)
            return usage
        except ImportError:
            return 0.0

    def get_cpu_info(self) -> dict:
        try:
            import psutil
            return {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "per_core": psutil.cpu_percent(interval=0.1, percpu=True),
            }
        except ImportError:
            return {"logical_cores": self.get_cpu_count()}

    def get_usage_history(self) -> list[float]:
        return list(self._usage_history)

    def get_avg_usage(self) -> float:
        if not self._usage_history:
            return 0.0
        return sum(self._usage_history) / len(self._usage_history)

    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, lambda: func(*args, **kwargs)
        )

    def submit_task(self, func: Callable, *args, **kwargs):
        return self._executor.submit(func, *args, **kwargs)

    def get_optimal_workers(self) -> int:
        cpu_count = self.get_cpu_count()
        usage = self.get_cpu_usage()
        if usage > 80:
            return max(1, cpu_count // 2)
        elif usage > 50:
            return max(2, cpu_count * 3 // 4)
        return cpu_count

    def get_stats(self) -> dict:
        return {
            "cpu_count": self.get_cpu_count(),
            "current_usage": self.get_cpu_usage(),
            "avg_usage": self.get_avg_usage(),
            "optimal_workers": self.get_optimal_workers(),
            "thread_pool_size": self.max_workers,
        }

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
