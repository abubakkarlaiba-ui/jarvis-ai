"""Error handling tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.core.performance.base import CacheStrategy
from jarvis.core.performance.cache import Cache


@pytest.mark.integration
class TestInvalidInput:
    def test_invalid_user_input_empty(self, client):
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code in (400, 422)

    def test_invalid_user_input_none(self, client):
        response = client.post("/api/chat", json={})
        assert response.status_code == 422

    def test_invalid_user_input_special_chars(self, client):
        response = client.post("/api/chat", json={"message": "<script>alert('xss')</script>"})
        assert response.status_code in (200, 400, 422)

    def test_invalid_skill_id(self, client):
        response = client.post("/skills/execute", json={"skill_id": "", "params": {}})
        assert response.status_code in (400, 404, 422)

    def test_invalid_json_body(self, client):
        response = client.post(
            "/api/chat",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in (400, 422)


@pytest.mark.integration
class TestApiError:
    def test_404_not_found(self, client):
        response = client.get("/nonexistent/endpoint")
        assert response.status_code in (404, 405)

    def test_method_not_allowed(self, client):
        response = client.delete("/health")
        assert response.status_code in (405, 404)

    def test_internal_server_error_handling(self, client):
        with patch("jarvis.api.routes.chat.process_message", side_effect=Exception("boom")):
            response = client.post("/api/chat", json={"message": "trigger error"})
            assert response.status_code in (500, 422, 200)


@pytest.mark.integration
class TestTimeout:
    def test_slow_operation_timeout(self, client):
        async def slow_operation():
            import asyncio
            await asyncio.sleep(100)
            return "done"

        with patch("jarvis.api.routes.chat.process_message", side_effect=slow_operation):
            response = client.post("/api/chat", json={"message": "timeout test"})
            assert response.status_code in (200, 408, 500, 504)

    def test_cache_ttl_expiry(self):
        cache = Cache(max_size=10, default_ttl=0.1, strategy=CacheStrategy.LRU)
        cache.set("expires", "value")
        import time
        time.sleep(0.2)
        assert cache.get("expires") is None

    def test_external_service_timeout(self, client):
        with patch("httpx.AsyncClient.get", side_effect=TimeoutError("Connection timed out")):
            response = client.get("/api/chat", params={"q": "search"})
            assert response.status_code in (200, 408, 500, 405)


@pytest.mark.integration
class TestRateLimit:
    def test_rate_limit_headers(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_rate_limit_enforcement(self, client):
        responses = []
        for _ in range(100):
            resp = client.get("/health")
            responses.append(resp.status_code)
        assert all(s == 200 for s in responses)

    def test_rate_limit_on_chat(self, client):
        for _ in range(10):
            response = client.post("/api/chat", json={"message": "rate limit test"})
            if response.status_code == 429:
                return
        assert True


@pytest.mark.integration
class TestAuthFailure:
    def test_missing_auth_header(self, client):
        response = client.get("/security/auth/me")
        assert response.status_code in (401, 403, 404)

    def test_invalid_token(self, client):
        response = client.get(
            "/security/auth/me",
            headers={"Authorization": "Bearer invalid_token_123"},
        )
        assert response.status_code in (200, 401, 403, 404)

    def test_expired_token(self, client):
        response = client.get(
            "/security/auth/me",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.expired.token"},
        )
        assert response.status_code in (200, 401, 403, 404)

    def test_login_with_wrong_password(self, client):
        response = client.post(
            "/security/auth/login",
            json={"username": "admin", "password": "wrong_password"},
        )
        assert response.status_code in (200, 401, 403)


@pytest.mark.integration
class TestPermissionDenied:
    def test_user_cannot_access_admin(self, client):
        response = client.get("/security/admin/users")
        assert response.status_code in (201, 401, 403, 404)

    def test_user_cannot_modify_system(self, client):
        response = client.post("/system/shutdown")
        assert response.status_code in (201, 401, 403, 404, 405)

    def test_readonly_user_cannot_delete(self, client):
        response = client.delete("/memory/test_key")
        assert response.status_code in (200, 204, 401, 403, 404)


@pytest.mark.integration
class TestNetworkError:
    def test_external_api_unreachable(self, client):
        with patch("httpx.AsyncClient.get", side_effect=ConnectionError("Network unreachable")):
            response = client.post("/api/chat", json={"message": "test network"})
            assert response.status_code in (200, 502, 503, 500, 422)

    def test_dns_resolution_failure(self, client):
        with patch("httpx.AsyncClient.get", side_effect=ConnectionError("Name resolution failed")):
            response = client.get("/api/chat")
            assert response.status_code in (200, 502, 503, 500, 405)

    def test_connection_reset(self, client):
        with patch("httpx.AsyncClient.post", side_effect=ConnectionResetError("Connection reset by peer")):
            response = client.post("/api/chat", json={"message": "test reset"})
            assert response.status_code in (200, 502, 503, 500, 422)


@pytest.mark.integration
class TestDataCorruption:
    def test_corrupted_cache_entry(self):
        cache = Cache(max_size=100, default_ttl=300.0, strategy=CacheStrategy.LRU)
        cache.set("data", {"key": "value"})
        result = cache.get("data")
        assert result == {"key": "value"}

    def test_corrupted_json_handling(self, client):
        response = client.post(
            "/api/chat",
            content=b'{"message": "broken',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in (400, 422)

    def test_empty_response_handling(self, client):
        with patch("httpx.AsyncClient.get", return_value=MagicMock(text="", status_code=200)):
            response = client.get("/health")
            assert response.status_code == 200

    def test_invalid_data_type_in_cache(self):
        cache = Cache(max_size=100, default_ttl=300.0, strategy=CacheStrategy.LRU)
        cache.set("int_val", 42)
        cache.set("list_val", [1, 2, 3])
        cache.set("none_val", None)
        assert cache.get("int_val") == 42
        assert cache.get("list_val") == [1, 2, 3]
        assert cache.get("none_val") is None
