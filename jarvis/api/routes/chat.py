"""
Chat route — primary interface for sending commands to JARVIS.
"""

from __future__ import annotations

import json
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming chat message from the user."""
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    session_id: str = Field(default="default", description="Session identifier")
    stream: bool = Field(default=False, description="Stream the response")
    context: dict = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    """Response from JARVIS to a chat message."""
    reply: str = Field(..., description="JARVIS response text")
    session_id: str = Field(..., description="Session identifier")
    emotion: str | None = Field(default=None, description="Detected user emotion")
    tools_used: list[str] = Field(default_factory=list, description="Tools used in response")
    metadata: dict = Field(default_factory=dict)
    requires_action: bool = Field(default=False)


class SessionInfo(BaseModel):
    """Session information."""
    id: str
    name: str
    message_count: int
    status: str


class EngineStatus(BaseModel):
    """Reasoning engine status."""
    initialized: bool
    metrics: dict
    sessions: dict
    personality: str
    tools: int


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message and return JARVIS's response.

    This is the primary endpoint for interacting with JARVIS.
    The message is processed through the full reasoning pipeline.
    """
    from jarvis.api.app import get_jarvis_core

    core = get_jarvis_core()

    if request.stream:
        return StreamingResponse(
            _stream_response(core, request),
            media_type="text/event-stream",
        )

    response = await core.reasoning.process(
        user_input=request.message,
        session_id=request.session_id,
        context=request.context,
    )

    return ChatResponse(
        reply=response.text,
        session_id=response.session_id,
        emotion=response.emotion.emotion.value if response.emotion else None,
        tools_used=response.tools_used,
        metadata=response.metadata,
        requires_action=response.requires_action,
    )


async def _stream_response(core, request: ChatRequest):
    """Generator for streaming chat responses via SSE."""
    try:
        async for token in core.reasoning.stream(
            user_input=request.message,
            session_id=request.session_id,
        ):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions() -> list[SessionInfo]:
    """List all active conversation sessions."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()

    sessions = core.reasoning.sessions.list_sessions()
    return [
        SessionInfo(
            id=s.id,
            name=s.name,
            message_count=s.message_count,
            status=s.status.name,
        )
        for s in sessions
    ]


@router.post("/sessions", response_model=SessionInfo)
async def create_session(name: str = "New Session") -> SessionInfo:
    """Create a new conversation session."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()

    session = core.reasoning.sessions.create_session(name=name)
    return SessionInfo(
        id=session.id,
        name=session.name,
        message_count=session.message_count,
        status=session.status.name,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a conversation session."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    success = core.reasoning.sessions.delete(session_id)
    return {"success": success, "session_id": session_id}


@router.get("/status", response_model=EngineStatus)
async def engine_status() -> EngineStatus:
    """Return reasoning engine status and metrics."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    status = core.reasoning.get_status()
    return EngineStatus(**status)


@router.get("/tools")
async def list_tools() -> list[dict]:
    """List all available tools."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    return core.reasoning.tools.list_tools()


@router.get("/personality")
async def list_personalities() -> list[dict]:
    """List all available personality profiles."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    return core.reasoning.personality.list_profiles()


@router.post("/personality/{name}")
async def set_personality(name: str) -> dict:
    """Switch the active personality profile."""
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    success = core.reasoning.personality.set_profile(name)
    return {"success": success, "personality": name}
