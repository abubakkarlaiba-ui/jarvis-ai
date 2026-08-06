"""Multi-tier caching with LRU, TTL, and disk persistence."""

import os
import time
import json
import threading
import hashlib
import pickle
import fnmatch
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class CacheConfig:
    max_memory_items: int = 1000
    default_ttl: float = 300.0
    eviction_policy: str = "lru"
    disk_cache_dir: str = ".cache"
    disk_cache_enabled: bool = True
    max_disk_size_mb: int = 500


class CacheManager:
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self._memory: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()
        self._disk_path = Path(self.config.disk_cache_dir)
        self._hits = 0
        self._misses = 0
        if self.config.disk_cache_enabled:
            self._disk_path.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Any:
        with self._lock:
            if key in self._memory:
                entry = self._memory[key]
                if self._is_expired(entry):
                    del self._memory[key]
                    self._misses += 1
                    return None
                self._memory.move_to_end(key)
                self._hits += 1
                return entry["value"]
            self._misses += 1
        if self.config.disk_cache_enabled:
            value = self._load_from_disk(key)
            if value is not None:
                with self._lock:
                    self._memory[key] = {
                        "value": value,
                        "expires_at": time.time() + self.config.default_ttl,
                        "tags": [],
                    }
                    self._memory.move_to_end(key)
                return value
        return None

    def set(self, key: str, value: Any, ttl: float = None, tags: list[str] = None):
        ttl = ttl if ttl is not None else self.config.default_ttl
        expires_at = time.time() + ttl
        with self._lock:
            self._memory[key] = {
                "value": value,
                "expires_at": expires_at,
                "tags": tags or [],
            }
            self._memory.move_to_end(key)
            while len(self._memory) > self.config.max_memory_items:
                self._evict()
        if self.config.disk_cache_enabled:
            self._save_to_disk(key, value)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._memory:
                del self._memory[key]
                return True
        return False

    def exists(self, key: str) -> bool:
        with self._lock:
            if key in self._memory:
                return not self._is_expired(self._memory[key])
        return False

    def clear(self):
        with self._lock:
            self._memory.clear()
        if self.config.disk_cache_enabled:
            self._cleanup_disk()

    def clear_by_tag(self, tag: str) -> int:
        count = 0
        with self._lock:
            to_delete = [k for k, v in self._memory.items() if tag in v.get("tags", [])]
            for k in to_delete:
                del self._memory[k]
                count += 1
        return count

    def get_or_set(self, key: str, factory: Callable, ttl: float = None) -> Any:
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def set_many(self, items: dict[str, Any], ttl: float = None):
        for key, value in items.items():
            self.set(key, value, ttl=ttl)

    def size(self) -> int:
        with self._lock:
            return len(self._memory)

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "size": self.size(),
            "memory_usage_bytes": sum(self._estimate_size(v) for v in self._memory.values()),
        }

    def cleanup(self) -> int:
        count = 0
        with self._lock:
            expired = [k for k, v in self._memory.items() if self._is_expired(v)]
            for k in expired:
                del self._memory[k]
                count += 1
        return count

    def get_keys(self, pattern: str = None) -> list[str]:
        with self._lock:
            keys = list(self._memory.keys())
        if pattern:
            keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
        return keys

    def _evict(self):
        if not self._memory:
            return
        if self.config.eviction_policy == "lru":
            self._memory.popitem(last=False)
        elif self.config.eviction_policy == "lfu":
            least_key = min(self._memory, key=lambda k: self._memory[k].get("access_count", 0))
            del self._memory[least_key]
        elif self.config.eviction_policy == "fifo":
            self._memory.popitem(last=False)

    def _estimate_size(self, value: Any) -> int:
        try:
            return len(pickle.dumps(value))
        except Exception:
            return 0

    def _save_to_disk(self, key: str, value: Any):
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        file_path = self._disk_path / f"{key_hash}.cache"
        try:
            data = {"key": key, "value": value, "timestamp": time.time()}
            with open(file_path, "wb") as f:
                pickle.dump(data, f)
        except Exception:
            pass

    def _load_from_disk(self, key: str) -> Any:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        file_path = self._disk_path / f"{key_hash}.cache"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "rb") as f:
                data = pickle.load(f)
            if time.time() - data["timestamp"] > self.config.default_ttl:
                file_path.unlink()
                return None
            return data["value"]
        except Exception:
            return None

    def _cleanup_disk(self):
        if not self._disk_path.exists():
            return
        for file_path in self._disk_path.glob("*.cache"):
            try:
                file_path.unlink()
            except Exception:
                pass

    def _is_expired(self, entry: dict) -> bool:
        return time.time() > entry.get("expires_at", 0)

    def decorate(self, ttl: float = None, tags: list[str] = None):
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = f"{func.__module__}.{func.__qualname__}:{args}:{kwargs}"
                value = self.get(cache_key)
                if value is not None:
                    return value
                value = func(*args, **kwargs)
                self.set(cache_key, value, ttl=ttl, tags=tags)
                return value
            return wrapper
        return decorator

    def invalidate(self, pattern: str):
        with self._lock:
            to_delete = [k for k in self._memory if fnmatch.fnmatch(k, pattern)]
            for k in to_delete:
                del self._memory[k]
