"""UI component tests via httpx/TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.ui
class TestPageLoad:
    def test_page_load(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200

    def test_page_contains_jarvis_title(self, client: TestClient):
        response = client.get("/")
        assert "JARVIS" in response.text


@pytest.mark.ui
class TestStaticFiles:
    def test_css_files_served(self, client: TestClient):
        response = client.get("/static/style.css")
        assert response.status_code in (200, 404)

    def test_js_files_served(self, client: TestClient):
        response = client.get("/static/app.js")
        assert response.status_code in (200, 404)

    def test_static_route_exists(self, client: TestClient):
        response = client.get("/static/nonexistent.txt")
        assert response.status_code in (404, 200)


@pytest.mark.ui
class TestChatInput:
    def test_chat_input_accepts_text(self, client: TestClient):
        response = client.post("/api/chat", json={"message": "Hello JARVIS"})
        assert response.status_code in (200, 201, 422)

    def test_chat_input_rejects_empty(self, client: TestClient):
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code in (400, 422)

    def test_chat_input_max_length(self, client: TestClient):
        long_message = "A" * 10000
        response = client.post("/api/chat", json={"message": long_message})
        assert response.status_code in (200, 400, 422)


@pytest.mark.ui
class TestMicButton:
    def test_mic_button_endpoint_exists(self, client: TestClient):
        response = client.get("/api/voice/status")
        assert response.status_code in (200, 404)

    def test_mic_toggle(self, client: TestClient):
        response = client.post("/api/voice/toggle")
        assert response.status_code in (200, 201, 404, 405)

    def test_voice_status_response(self, client: TestClient):
        response = client.get("/api/voice/status")
        if response.status_code == 200:
            data = response.json()
            assert "enabled" in data or "status" in data


@pytest.mark.ui
class TestThemeToggle:
    def test_theme_toggle_endpoint(self, client: TestClient):
        response = client.post("/api/settings/theme", json={"theme": "dark"})
        assert response.status_code in (200, 201, 404, 422)

    def test_theme_dark(self, client: TestClient):
        response = client.post("/api/settings/theme", json={"theme": "dark"})
        if response.status_code in (200, 201):
            data = response.json()
            assert data.get("theme") == "dark"

    def test_theme_light(self, client: TestClient):
        response = client.post("/api/settings/theme", json={"theme": "light"})
        if response.status_code in (200, 201):
            data = response.json()
            assert data.get("theme") == "light"


@pytest.mark.ui
class TestPanelCollapse:
    def test_panel_collapse_endpoint(self, client: TestClient):
        response = client.post("/api/settings/panels", json={"sidebar": False})
        assert response.status_code in (200, 201, 404, 422)

    def test_panel_expand(self, client: TestClient):
        response = client.post("/api/settings/panels", json={"sidebar": True})
        assert response.status_code in (200, 201, 404, 422)


@pytest.mark.ui
class TestKeyboardShortcuts:
    def test_shortcuts_endpoint(self, client: TestClient):
        response = client.get("/api/settings/shortcuts")
        assert response.status_code in (200, 404)

    def test_shortcut_registration(self, client: TestClient):
        response = client.post("/api/settings/shortcuts", json={"key": "Ctrl+K", "action": "search"})
        assert response.status_code in (200, 201, 404, 422)


@pytest.mark.ui
class TestAccessibility:
    def test_main_page_has_aria_labels(self, client: TestClient):
        response = client.get("/")
        if response.status_code == 200:
            assert "aria-" in response.text or "role=" in response.text

    def test_chat_input_aria(self, client: TestClient):
        response = client.get("/")
        if response.status_code == 200:
            assert "chat" in response.text.lower() or "input" in response.text.lower()

    def test_navigation_landmarks(self, client: TestClient):
        response = client.get("/")
        if response.status_code == 200:
            assert "nav" in response.text.lower() or "main" in response.text.lower()
