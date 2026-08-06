"""
Performance module — circuit breaker pattern and error recovery.
================================================================
Provides fault tolerance through circuit breakers, retries, and fallbacks.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from enum import Enum, auto
from typing import Any, Callable

from jarvis.core.performance.base import PerformanceSnapshot


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitBreaker:
    """A single circuit breaker instance."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30,
        half_open_max: int = 3,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.total_calls: int = 0
        self.last_failure_time: float = 0.0
        self.half_open_calls: int = 0
        self.history: deque = deque(maxlen=100)
        self.fallback_func: Callable | None = None

    def record_failure(self) -> None:
        self.failure_count += 1
        self.total_calls += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max:
                self._trip()
        elif self.failure_count >= self.failure_threshold:
            self._trip()

    def record_success(self) -> None:
        self.success_count += 1
        self.total_calls += 1

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.half_open_calls = 0

    def _trip(self) -> None:
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()

    def is_open(self) -> bool:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return False
            return True
        return False

    def reset(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.total_calls = 0
        self.last_failure_time = 0.0
        self.half_open_calls = 0
        self.history.clear()

    def get_state_name(self) -> str:
        return self.state.name.lower()

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.get_state_name(),
            "total_calls": self.total_calls,
            "failures": self.failure_count,
            "successes": self.success_count,
            "half_open_calls": self.half_open_calls,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time,
        }


class ErrorRecovery:
    """Circuit breaker pattern and error recovery manager."""

    def __init__(self) -> None:
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.event_log: deque = deque(maxlen=500)

    def create_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30,
        half_open_max: int = 3,
    ) -> None:
        if name in self.circuit_breakers:
            self._log_event(name, "recreated", {"old_state": self.circuit_breakers[name].get_state_name()})
        self.circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max=half_open_max,
        )
        self._log_event(name, "created", {"threshold": failure_threshold, "timeout": recovery_timeout})

    def _get_breaker(self, name: str) -> CircuitBreaker:
        if name not in self.circuit_breakers:
            raise KeyError(f"Circuit breaker '{name}' not found")
        return self.circuit_breakers[name]

    def call(self, name: str, func: Callable, *args, **kwargs) -> Any:
        breaker = self._get_breaker(name)

        if breaker.is_open():
            self._log_event(name, "rejected", {"reason": "circuit_open"})
            if breaker.fallback_func is not None:
                return breaker.fallback_func(*args, **kwargs)
            raise RuntimeError(f"Circuit breaker '{name}' is open")

        try:
            result = func(*args, **kwargs)
            breaker.record_success()
            self._log_event(name, "success", {})
            return result
        except Exception as e:
            breaker.record_failure()
            self._log_event(name, "failure", {"error": str(e)})
            if breaker.fallback_func is not None:
                return breaker.fallback_func(*args, **kwargs)
            raise

    async def async_call(self, name: str, coro) -> Any:
        breaker = self._get_breaker(name)

        if breaker.is_open():
            self._log_event(name, "rejected", {"reason": "circuit_open"})
            if breaker.fallback_func is not None:
                return await breaker.fallback_func() if asyncio.iscoroutinefunction(breaker.fallback_func) else breaker.fallback_func()
            raise RuntimeError(f"Circuit breaker '{name}' is open")

        try:
            result = await coro
            breaker.record_success()
            self._log_event(name, "success", {})
            return result
        except Exception as e:
            breaker.record_failure()
            self._log_event(name, "failure", {"error": str(e)})
            if breaker.fallback_func is not None:
                return await breaker.fallback_func() if asyncio.iscoroutinefunction(breaker.fallback_func) else breaker.fallback_func()
            raise

    def get_state(self, name: str) -> str:
        return self._get_breaker(name).get_state_name()

    def reset(self, name: str) -> None:
        breaker = self._get_breaker(name)
        breaker.reset()
        self._log_event(name, "reset", {})

    def record_failure(self, name: str) -> None:
        self._get_breaker(name).record_failure()
        self._log_event(name, "manual_failure", {})

    def record_success(self, name: str) -> None:
        self._get_breaker(name).record_success()
        self._log_event(name, "manual_success", {})

    def is_open(self, name: str) -> bool:
        return self._get_breaker(name).is_open()

    def create_fallback(self, name: str, fallback_func: Callable) -> None:
        breaker = self._get_breaker(name)
        breaker.fallback_func = fallback_func
        self._log_event(name, "fallback_registered", {})

    @staticmethod
    def with_retry(
        func: Callable,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,),
    ) -> Any:
        last_exc: Exception | None = None
        current_delay = delay

        for attempt in range(max_retries + 1):
            try:
                return func()
            except exceptions as e:
                last_exc = e
                if attempt < max_retries:
                    time.sleep(current_delay)
                    current_delay *= backoff

        raise last_exc  # type: ignore[misc]

    @staticmethod
    async def with_async_retry(
        coro,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
    ) -> Any:
        last_exc: Exception | None = None
        current_delay = delay

        for attempt in range(max_retries + 1):
            try:
                return await coro
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

        raise last_exc  # type: ignore[misc]

    def get_stats(self) -> dict:
        stats = {}
        for name, breaker in self.circuit_breakers.items():
            stats[name] = breaker.get_stats()
        return stats

    def get_all_states(self) -> dict:
        return {
            name: breaker.get_state_name()
            for name, breaker in self.circuit_breakers.items()
        }

    def _log_event(self, name: str, event: str, details: dict | None = None) -> None:
        entry = {
            "timestamp": time.time(),
            "breaker": name,
            "event": event,
            "details": details or {},
        }
        self.event_log.append(entry)
