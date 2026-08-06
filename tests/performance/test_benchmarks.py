"""Performance benchmark tests."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from jarvis.core.performance.base import CacheStrategy
from jarvis.core.performance.cache import Cache


@pytest.mark.performance
class TestCacheThroughput:
    def test_cache_set_throughput(self):
        cache = Cache(max_size=10000, default_ttl=300.0, strategy=CacheStrategy.LRU)
        start = time.perf_counter()
        for i in range(10000):
            cache.set(f"key_{i}", f"value_{i}")
        elapsed = time.perf_counter() - start
        ops_per_sec = 10000 / elapsed
        assert ops_per_sec > 1000, f"Cache set too slow: {ops_per_sec:.0f} ops/s"

    def test_cache_get_throughput(self):
        cache = Cache(max_size=10000, default_ttl=300.0, strategy=CacheStrategy.LRU)
        for i in range(10000):
            cache.set(f"key_{i}", f"value_{i}")
        start = time.perf_counter()
        for i in range(10000):
            cache.get(f"key_{i}")
        elapsed = time.perf_counter() - start
        ops_per_sec = 10000 / elapsed
        assert ops_per_sec > 1000, f"Cache get too slow: {ops_per_sec:.0f} ops/s"

    def test_cache_mixed_throughput(self):
        cache = Cache(max_size=10000, default_ttl=300.0, strategy=CacheStrategy.LRU)
        start = time.perf_counter()
        for i in range(5000):
            cache.set(f"key_{i}", f"value_{i}")
            cache.get(f"key_{i}")
        elapsed = time.perf_counter() - start
        ops_per_sec = 10000 / elapsed
        assert ops_per_sec > 1000, f"Mixed ops too slow: {ops_per_sec:.0f} ops/s"


@pytest.mark.performance
class TestEncryptionSpeed:
    def test_encryption_speed(self, tmp_path):
        from jarvis.core.security.encryption import EncryptionManager
        key_file = tmp_path / "bench.key"
        enc = EncryptionManager(key_file=str(key_file))

        plaintext = "The quick brown fox jumps over the lazy dog. " * 10
        iterations = 500

        start = time.perf_counter()
        for _ in range(iterations):
            enc.encrypt(plaintext)
        elapsed = time.perf_counter() - start
        ops_per_sec = iterations / elapsed
        assert ops_per_sec > 10, f"Encryption too slow: {ops_per_sec:.0f} ops/s"

    def test_decryption_speed(self, tmp_path):
        from jarvis.core.security.encryption import EncryptionManager
        key_file = tmp_path / "bench.key"
        enc = EncryptionManager(key_file=str(key_file))

        plaintext = "The quick brown fox jumps over the lazy dog. " * 10
        ciphertext = enc.encrypt(plaintext)
        iterations = 500

        start = time.perf_counter()
        for _ in range(iterations):
            enc.decrypt(ciphertext)
        elapsed = time.perf_counter() - start
        ops_per_sec = iterations / elapsed
        assert ops_per_sec > 10, f"Decryption too slow: {ops_per_sec:.0f} ops/s"

    def test_hash_speed(self, tmp_path):
        from jarvis.core.security.encryption import EncryptionManager
        key_file = tmp_path / "bench.key"
        enc = EncryptionManager(key_file=str(key_file))

        data = "Test data for hashing benchmark"
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            enc.hash_data(data)
        elapsed = time.perf_counter() - start
        ops_per_sec = iterations / elapsed
        assert ops_per_sec > 100, f"Hashing too slow: {ops_per_sec:.0f} ops/s"


@pytest.mark.performance
class TestApiResponseTime:
    def test_health_endpoint_latency(self, client):
        start = time.perf_counter()
        response = client.get("/health")
        elapsed = time.perf_counter() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"Health endpoint too slow: {elapsed:.3f}s"

    def test_skills_endpoint_latency(self, client):
        start = time.perf_counter()
        response = client.get("/skills/")
        elapsed = time.perf_counter() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"Skills endpoint too slow: {elapsed:.3f}s"

    def test_memory_endpoint_latency(self, client):
        start = time.perf_counter()
        response = client.get("/memory/")
        elapsed = time.perf_counter() - start
        assert response.status_code in (200, 404)
        assert elapsed < 2.0, f"Memory endpoint too slow: {elapsed:.3f}s"


@pytest.mark.performance
class TestConcurrentRequests:
    def test_concurrent_get_requests(self, client):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def make_request(path):
            return client.get(path)

        paths = ["/health"] * 20
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, p) for p in paths]
            results = [f.result() for f in as_completed(futures)]

        assert all(r.status_code == 200 for r in results)

    def test_concurrent_chat_requests(self, client):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def send_message(msg):
            return client.post("/api/chat", json={"message": msg})

        messages = [f"Message {i}" for i in range(5)]
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_message, m) for m in messages]
            results = [f.result() for f in as_completed(futures)]

        assert all(r.status_code in (200, 201, 429, 422) for r in results)


@pytest.mark.performance
class TestMemoryEfficiency:
    def test_cache_memory_usage(self):
        cache = Cache(max_size=5000, default_ttl=300.0, strategy=CacheStrategy.LRU)
        for i in range(1000):
            cache.set(f"key_{i}", "x" * 100)
        usage = cache.memory_usage()
        assert usage > 0
        assert usage < 10 * 1024 * 1024, f"Cache using too much memory: {usage / 1024:.1f} KB"

    def test_cache_memory_after_clear(self):
        cache = Cache(max_size=5000, default_ttl=300.0, strategy=CacheStrategy.LRU)
        for i in range(1000):
            cache.set(f"key_{i}", "x" * 100)
        cache.clear()
        usage = cache.memory_usage()
        assert usage < 1024, f"Cache not cleared properly: {usage} bytes"


@pytest.mark.performance
class TestStartupTime:
    def test_import_time(self):
        start = time.perf_counter()
        import jarvis
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Import too slow: {elapsed:.3f}s"

    def test_app_creation_time(self, client):
        start = time.perf_counter()
        client.get("/health")
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"App not ready in time: {elapsed:.3f}s"
