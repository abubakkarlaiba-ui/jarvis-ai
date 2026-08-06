"""
Utility decorators for JARVIS.
==============================
Reusable decorators for timing, caching, validation, and error handling.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


def log_execution(func: Callable) -> Callable:
    """Decorator that logs function entry, exit, and execution time.

    Works with both sync and async functions.

    Example:
        @log_execution
        async def process_command(text: str) -> str: ...
    """
    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = f"{func.__module__}.{func.__qualname__}"
        logger.debug("Entering %s", func_name)
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.debug("Exiting %s (%.4fs)", func_name, elapsed)
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error("Error in %s after %.4fs: %s", func_name, elapsed, exc)
            raise

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = f"{func.__module__}.{func.__qualname__}"
        logger.debug("Entering %s", func_name)
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.debug("Exiting %s (%.4fs)", func_name, elapsed)
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error("Error in %s after %.4fs: %s", func_name, elapsed, exc)
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def cache_result(ttl_seconds: float = 300.0) -> Callable:
    """Decorator that caches function results for a fixed duration.

    Args:
        ttl_seconds: Time-to-live for cached values. Default 300s.

    Example:
        @cache_result(ttl_seconds=60)
        async def get_user(user_id: str) -> dict: ...
    """
    def decorator(func: Callable) -> Callable:
        _cache: dict[str, tuple[float, Any]] = {}

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = str(args) + str(sorted(kwargs.items()))
            now = time.monotonic()
            if key in _cache:
                cached_time, cached_value = _cache[key]
                if now - cached_time < ttl_seconds:
                    return cached_value
            result = await func(*args, **kwargs)
            _cache[key] = (now, result)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = str(args) + str(sorted(kwargs.items()))
            now = time.monotonic()
            if key in _cache:
                cached_time, cached_value = _cache[key]
                if now - cached_time < ttl_seconds:
                    return cached_value
            result = func(*args, **kwargs)
            _cache[key] = (now, result)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def require_features(*feature_names: str) -> Callable:
    """Decorator that raises if required features are not enabled.

    Checks the application settings to ensure named features are active
    before executing the decorated function.

    Args:
        *feature_names: Names of features that must be enabled.

    Example:
        @require_features("voice.enabled", "ai.api_key")
        async def listen_for_command(): ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            from jarvis.config import get_settings
            settings = get_settings()
            for feature in feature_names:
                parts = feature.split(".")
                obj = settings
                for part in parts:
                    obj = getattr(obj, part, None)
                    if obj is None:
                        raise RuntimeError(
                            f"Feature '{feature}' is not enabled. "
                            f"Cannot execute {func.__qualname__}."
                        )
                if not obj:
                    raise RuntimeError(
                        f"Feature '{feature}' is disabled. "
                        f"Cannot execute {func.__qualname__}."
                    )
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            from jarvis.config import get_settings
            settings = get_settings()
            for feature in feature_names:
                parts = feature.split(".")
                obj = settings
                for part in parts:
                    obj = getattr(obj, part, None)
                    if obj is None:
                        raise RuntimeError(
                            f"Feature '{feature}' is not enabled. "
                            f"Cannot execute {func.__qualname__}."
                        )
                if not obj:
                    raise RuntimeError(
                        f"Feature '{feature}' is disabled. "
                        f"Cannot execute {func.__qualname__}."
                    )
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
