"""Unit tests for the Cache module."""

from __future__ import annotations

import time

import pytest

from jarvis.core.performance.base import CacheStrategy
from jarvis.core.performance.cache import Cache


@pytest.fixture
def cache():
    return Cache(max_size=10, default_ttl=60.0, strategy=CacheStrategy.LRU)


@pytest.mark.unit
class TestCache:
    def test_set_get(self, cache):
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing(self, cache):
        assert cache.get("nonexistent") is None

    def test_delete(self, cache):
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_ttl_expiry(self, cache):
        cache.set("key1", "value1", ttl=0.1)
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        small_cache = Cache(max_size=3, default_ttl=60.0, strategy=CacheStrategy.LRU)
        small_cache.set("a", 1)
        small_cache.set("b", 2)
        small_cache.set("c", 3)
        small_cache.set("d", 4)  # should evict "a"
        assert small_cache.get("a") is None
        assert small_cache.get("d") == 4

    def test_cache_stats(self, cache):
        cache.get("miss")
        cache.set("hit_key", "val")
        cache.get("hit_key")
        stats = cache.get_stats()
        assert stats["misses"] >= 1
        assert stats["hits"] >= 1

    def test_decorator(self, cache):
        call_count = 0

        @cache.decorator()
        def expensive_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_func(5)
        result2 = expensive_func(5)
        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    def test_clear(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        count = cache.clear()
        assert count == 2
        assert cache.size() == 0

    def test_exists(self, cache):
        cache.set("key1", "value1")
        assert cache.exists("key1") is True
        assert cache.exists("missing") is False

    def test_memory_usage(self, cache):
        cache.set("key1", "value1")
        usage = cache.memory_usage()
        assert usage > 0
