"""
Shared test fixtures for the JARVIS test suite.
===============================================
Provides reusable fixtures for all test categories.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Temporary directories ─────────────────────────────────────────


@pytest.fixture
def temp_dir():
    """Create a temporary directory, cleaned up after test."""
    d = tempfile.mkdtemp(prefix="jarvis_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def temp_data_dir(temp_dir):
    """Create a temporary data directory structure."""
    dirs = [
        "data/memory",
        "data/skills",
        "data/workflows",
        "data/security",
        "data/backups",
        "data/voice_logs",
        "data/screenshots",
        "data/vision_cache",
        "data/performance",
        "plugins",
        "logs",
    ]
    for d in dirs:
        (temp_dir / d).mkdir(parents=True, exist_ok=True)
    return temp_dir


@pytest.fixture
def fixtures_dir():
    """Return the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


# ── Mock objects ──────────────────────────────────────────────────


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    from jarvis.core.security.base import User
    return User(
        id="test_user_001",
        username="testuser",
        email="test@jarvis.ai",
        password_hash="hash123",
        salt="salt123",
        roles=["user"],
        is_active=True,
    )


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    from jarvis.core.security.base import User
    return User(
        id="admin_001",
        username="admin",
        email="admin@jarvis.ai",
        password_hash="hash_admin",
        salt="salt_admin",
        roles=["admin"],
        is_active=True,
    )


@pytest.fixture
def mock_skill():
    """Create a mock skill."""
    from jarvis.core.skills.module import BaseSkill, SkillMetadata, SkillResult

    class MockSkill(BaseSkill):
        metadata = SkillMetadata(
            name="test_skill",
            version="1.0.0",
            description="A test skill",
            tags=["test"],
        )

        async def execute(self, context):
            return SkillResult(
                success=True,
                output=f"Executed with: {context.user_input}",
            )

    return MockSkill


@pytest.fixture
def mock_step():
    """Create a mock workflow step."""
    from jarvis.core.workflow.base import Step, StepType, StepRisk
    return Step(
        name="test_step",
        step_type=StepType.CODE,
        command="print('hello')",
        risk=StepRisk.LOW,
    )


@pytest.fixture
def mock_workflow():
    """Create a mock workflow."""
    from jarvis.core.workflow.base import Workflow, Step, StepType
    return Workflow(
        id="wf_test_001",
        name="Test Workflow",
        steps=[
            Step(name="step1", step_type=StepType.CODE, command="print('1')"),
            Step(name="step2", step_type=StepType.CODE, command="print('2')", depends_on=["step1"]),
        ],
    )


@pytest.fixture
def mock_api_response():
    """Create a mock API response."""
    return {
        "status": "success",
        "data": {"message": "OK"},
        "timestamp": "2026-01-01T00:00:00Z",
    }


# ── Mock services ─────────────────────────────────────────────────


@pytest.fixture
def mock_openai():
    """Mock OpenAI API calls."""
    mock = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(
            message=MagicMock(content="Test response"),
            finish_reason="stop",
        )],
        usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ))
    mock.embeddings.create = AsyncMock(return_value=MagicMock(
        data=[MagicMock(embedding=[0.1] * 1536)],
    ))
    return mock


@pytest.fixture
def mock_httpx():
    """Mock httpx HTTP client."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value={"status": "ok"}),
        text="OK",
    ))
    mock.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value={"status": "ok"}),
    ))
    return mock


@pytest.fixture
def mock_psutil():
    """Mock psutil system info."""
    with patch("psutil.cpu_percent", return_value=45.0), \
         patch("psutil.virtual_memory") as mock_mem, \
         patch("psutil.disk_usage") as mock_disk:
        mock_mem.return_value = MagicMock(
            total=16 * 1024**3,
            used=8 * 1024**3,
            available=8 * 1024**3,
            percent=50.0,
        )
        mock_disk.return_value = MagicMock(
            total=500 * 1024**3,
            used=200 * 1024**3,
            free=300 * 1024**3,
            percent=40.0,
        )
        yield


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock(return_value={"type": "message", "content": "test"})
    ws.close = AsyncMock()
    ws.state = "connected"
    return ws


# ── Sample data ───────────────────────────────────────────────────


@pytest.fixture
def sample_code_python():
    return '''
def hello_world():
    """Say hello."""
    print("Hello, World!")
    return "Hello"

class Calculator:
    def add(self, a, b):
        return a + b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
'''


@pytest.fixture
def sample_code_javascript():
    return '''
function helloWorld() {
    console.log("Hello, World!");
    return "Hello";
}

class Calculator {
    add(a, b) { return a + b; }
    divide(a, b) {
        if (b === 0) throw new Error("Cannot divide by zero");
        return a / b;
    }
}
'''


@pytest.fixture
def sample_markdown():
    return '''# Test Document

## Section 1
This is a **bold** and *italic* text.

## Code Example
```python
def test():
    pass
```

## Links
[Example](https://example.com)
'''


@pytest.fixture
def sample_api_spec():
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {"summary": "List users"},
                "post": {"summary": "Create user"},
            }
        },
    }


# ── Async helpers ─────────────────────────────────────────────────


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def run_async():
    """Helper to run async functions in tests."""
    def _run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    return _run


# ── Environment helpers ───────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Isolate environment variables for each test."""
    monkeypatch.setenv("JARVIS_TESTING", "1")
    monkeypatch.setenv("JARVIS_DATA_DIR", "")
    yield


@pytest.fixture
def mock_settings():
    """Mock JARVIS settings."""
    settings = MagicMock()
    settings.ai_model = "gpt-4o"
    settings.voice_enabled = False
    settings.memory_enabled = True
    settings.debug = True
    return settings
