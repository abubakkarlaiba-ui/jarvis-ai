"""
Performance module — in-memory TTL/LRU cache with multiple eviction strategies.
===============================================================================
Thread-safe cache supporting LRU, LFU, and FIFO eviction with optional TTL.
"""

from __future__ import annotations

import functools
import sys
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

from jarvis.core.performance.base import CacheEntry, CacheStrategy


class Cache:
    """In-memory TTL/LRU cache with multiple eviction strategies."""

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,
        strategy: CacheStrategy = CacheStrategy.LRU,
    ) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._strategy = strategy
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

    def get(self, key: str) -> Any:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None
            if entry.is_expired:
                del self._entries[key]
                self._stats["misses"] += 1
                return None
            entry.last_accessed = time.time()
            entry.access_count += 1
            if self._strategy == CacheStrategy.LRU:
                self._entries.move_to_end(key)
            self._stats["hits"] += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        size_bytes: int = 0,
    ) -> None:
        effective_ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            if key in self._entries:
                del self._entries[key]
            elif len(self._entries) >= self._max_size:
                self._evict()
            self._entries[key] = CacheEntry(
                key=key,
                value=value,
                ttl=effective_ttl,
                size_bytes=size_bytes,
            )

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._entries[key]
                return False
            return True

    def clear(self) -> int:
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count

    def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: float | None = None,
    ) -> Any:
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def ttl(self, key: str) -> float:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return -2.0
            if entry.ttl <= 0:
                return -1.0
            remaining = entry.ttl - (time.time() - entry.created_at)
            if remaining <= 0:
                del self._entries[key]
                return -2.0
            return remaining

    def keys(self) -> list[str]:
        with self._lock:
            now = time.time()
            expired = [
                k
                for k, e in self._entries.items()
                if e.ttl > 0 and (now - e.created_at) > e.ttl
            ]
            for k in expired:
                del self._entries[k]
            return list(self._entries.keys())

    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def memory_usage(self) -> int:
        with self._lock:
            return sum(
                sys.getsizeof(k) + sys.getsizeof(v) + e.size_bytes
                for k, e in self._entries.items()
                for v in (e.value,)
            )

    def _evict(self) -> None:
        if self._strategy == CacheStrategy.LRU:
            self._evict_lru()
        elif self._strategy == CacheStrategy.LFU:
            self._evict_lfu()
        else:
            self._evict_fifo()
        self._stats["evictions"] += 1

    def _evict_lru(self) -> str:
        key, _ = self._entries.popitem(last=False)
        return key

    def _evict_lfu(self) -> str:
        least_key = min(
            self._entries,
            key=lambda k: self._entries[k].access_count,
        )
        del self._entries[least_key]
        return least_key

    def _evict_fifo(self) -> str:
        key, _ = self._entries.popitem(last=False)
        return key

    def cleanup_expired(self) -> int:
        with self._lock:
            now = time.time()
            expired = [
                k
                for k, e in self._entries.items()
                if e.ttl > 0 and (now - e.created_at) > e.ttl
            ]
            for k in expired:
                del self._entries[k]
            return len(expired)

    def get_stats(self) -> dict:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0.0
            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": hit_rate,
                "evictions": self._stats["evictions"],
                "size": len(self._entries),
            }

    def decorator(self, ttl: float | None = None) -> Callable:
        def wrapper(func: Callable) -> Callable:
            @functools.wraps(func)
            def inner(*args: Any, **kwargs: Any) -> Any:
                cache_key = f"{func.__module__}:{func.__qualname__}:{args}:{kwargs}"
                result = self.get(cache_key)
                if result is not None:
                    return result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl=ttl)
                return result
            return inner
        return wrapper
