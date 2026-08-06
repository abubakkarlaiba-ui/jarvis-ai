import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestHealthEndpoint:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200


@pytest.mark.integration
class TestSkillsRoutes:
    def test_skills_list(self, client):
        response = client.get("/skills/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    def test_skill_execute(self, client):
        payload = {"skill_id": "test_skill", "params": {}}
        response = client.post("/skills/execute", json=payload)
        assert response.status_code in (200, 201, 404, 422)


@pytest.mark.integration
class TestMemoryRoutes:
    def test_memory_routes(self, client):
        get_resp = client.get("/memory/")
        assert get_resp.status_code in (200, 404)

        post_resp = client.post("/memory/", json={"key": "test", "value": "data"})
        assert post_resp.status_code in (200, 201, 422)


@pytest.mark.integration
class TestWorkflowRoutes:
    def test_workflow_create(self, client):
        payload = {"name": "test_workflow", "steps": []}
        response = client.post("/workflow/create", json=payload)
        assert response.status_code in (200, 201)

    def test_workflow_plan(self, client):
        payload = {"goal": "Analyze sales data"}
        response = client.post("/workflow/plan", json=payload)
        assert response.status_code in (200, 201, 422)


@pytest.mark.integration
class TestSecurityRoutes:
    def test_security_register(self, client):
        payload = {"username": "testuser", "password": "testpass123"}
        response = client.post("/security/auth/register", json=payload)
        assert response.status_code in (200, 201, 409)

    def test_security_login(self, client):
        payload = {"username": "testuser", "password": "testpass123"}
        response = client.post("/security/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data


@pytest.mark.integration
class TestPerformanceRoutes:
    def test_performance_health(self, client):
        response = client.get("/performance/health")
        assert response.status_code == 200

    def test_cache_operations(self, client):
        post_resp = client.post("/performance/cache", json={"key": "k", "value": "v"})
        assert post_resp.status_code in (200, 201, 422)

        get_resp = client.get("/performance/cache/k")
        assert get_resp.status_code in (200, 404)

        del_resp = client.delete("/performance/cache/k")
        assert del_resp.status_code in (200, 204, 404)
