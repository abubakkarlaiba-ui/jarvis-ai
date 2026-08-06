"""
Utility helpers for JARVIS.
===========================
General-purpose helper functions used across the codebase.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def utc_now() -> datetime:
    """Return the current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> float:
    """Return current UTC time as a Unix timestamp."""
    return utc_now().timestamp()


def hash_text(text: str, algorithm: str = "sha256") -> str:
    """Compute a hex digest hash of the given text.

    Args:
        text: Input string to hash.
        algorithm: Hash algorithm name (sha256, md5, etc.).

    Returns:
        Hex-encoded hash string.
    """
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def ensure_directory(path: str | Path) -> Path:
    """Create the directory at path if it does not exist and return it.

    Args:
        path: Directory path to ensure.

    Returns:
        Resolved Path object.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (mutates base).

    Args:
        base: Dictionary to merge into.
        override: Dictionary whose values take precedence.

    Returns:
        The merged base dictionary.
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def safe_json_loads(text: str, default: Any = None) -> Any:
    """Parse JSON safely, returning a default on failure.

    Args:
        text: JSON string to parse.
        default: Value to return if parsing fails.

    Returns:
        Parsed data or the default value.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator that retries a function on specified exceptions.

    Args:
        max_attempts: Maximum number of attempts.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to delay after each retry.
        exceptions: Tuple of exception types to catch and retry on.

    Returns:
        Decorated function with retry logic.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt < max_attempts:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception  # type: ignore[misc]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception  # type: ignore[misc]

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class Timer:
    """Context manager that measures elapsed time.

    Example:
        with Timer() as t:
            do_work()
        print(f"Elapsed: {t.elapsed:.2f}s")
    """

    def __init__(self):
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def __enter__(self) -> Timer:
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.end_time = time.perf_counter()

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.perf_counter() - self.start_time
