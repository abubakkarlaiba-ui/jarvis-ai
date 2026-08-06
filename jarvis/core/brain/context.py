"""
Context awareness engine for JARVIS.
=====================================
Builds and maintains a rich understanding of the current situation,
including user state, environment, conversation topic, and temporal context.

The context engine answers: "What does JARVIS need to know right now?"

It assembles a context snapshot that is injected into the system prompt,
giving the LLM situational awareness beyond just the conversation history.

Usage:
    context = ContextEngine(settings)
    snapshot = await context.build_snapshot(session_id, memory, user_input)
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from jarvis.config.settings import AISettings
from jarvis.utils.helpers import utc_now

logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """Information about the current user and their state."""
    user_id: str = "default"
    name: str = ""
    preferred_name: str = ""
    timezone: str = "UTC"
    current_emotion: str = "neutral"
    interaction_count: int = 0
    last_interaction: datetime | None = None
    preferences: dict[str, Any] = field(default_factory=dict)
    expertise_level: str = "intermediate"  # novice, intermediate, expert


@dataclass
class EnvironmentContext:
    """System and environment information."""
    platform: str = ""
    time_of_day: str = ""
    hour: int = 0
    day_of_week: str = ""
    is_weekend: bool = False
    active_applications: list[str] = field(default_factory=list)
    system_load: float = 0.0


@dataclass
class ConversationContext:
    """Current conversation state."""
    topic: str = ""
    sub_topic: str = ""
    turn_count: int = 0
    sentiment: str = "neutral"
    urgency: str = "normal"  # low, normal, high, critical
    task_in_progress: str = ""
    pending_questions: list[str] = field(default_factory=list)
    mentioned_entities: dict[str, str] = field(default_factory=dict)


@dataclass
class ContextSnapshot:
    """Complete context snapshot for a reasoning request."""
    user: UserContext
    environment: EnvironmentContext
    conversation: ConversationContext
    long_term_facts: list[str] = field(default_factory=list)
    active_skills: list[str] = field(default_factory=list)
    raw_text: str = ""

    def to_prompt_section(self) -> str:
        """Convert to a formatted string for system prompt injection."""
        parts = []

        # Time context
        parts.append(f"Time: {self.environment.time_of_day}, {self.environment.day_of_week}")
        if self.environment.is_weekend:
            parts.append("It is currently the weekend.")

        # User context
        if self.user.name:
            parts.append(f"User: {self.user.name} ({self.user.preferred_name or self.user.name})")
        parts.append(f"User expertise: {self.user.expertise_level}")
        if self.user.current_emotion != "neutral":
            parts.append(f"User appears {self.user.current_emotion}")
        if self.user.interaction_count > 0:
            parts.append(f"This is interaction #{self.user.interaction_count}")

        # Conversation context
        if self.conversation.topic:
            parts.append(f"Current topic: {self.conversation.topic}")
        if self.conversation.urgency != "normal":
            parts.append(f"Urgency: {self.conversation.urgency}")
        if self.conversation.task_in_progress:
            parts.append(f"Task in progress: {self.conversation.task_in_progress}")

        # Long-term facts
        if self.long_term_facts:
            parts.append("Known facts about the user:")
            for fact in self.long_term_facts[:5]:
                parts.append(f"  - {fact}")

        return "\n".join(parts)


class ContextEngine:
    """Builds and maintains contextual awareness for reasoning.

    The context engine runs before each reasoning cycle to assemble
    a snapshot of everything JARVIS knows about the current situation.

    Example:
        engine = ContextEngine(settings)
        snapshot = await engine.build_snapshot("session-1", memory, "What's up?")
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._user_contexts: dict[str, UserContext] = {}
        self._conversation_contexts: dict[str, ConversationContext] = {}
        self._topic_history: dict[str, list[str]] = {}

    async def build_snapshot(
        self,
        session_id: str,
        memory: Any | None = None,
        user_input: str = "",
    ) -> ContextSnapshot:
        """Build a complete context snapshot for the current turn.

        Args:
            session_id: Session identifier.
            memory: ConversationMemory instance for fact lookup.
            user_input: The user's current message.

        Returns:
            A fully assembled ContextSnapshot.
        """
        now = utc_now()

        user = self._get_user_context(session_id)
        user.interaction_count += 1
        user.last_interaction = now

        environment = self._build_environment_context(now)
        conversation = self._get_conversation_context(session_id)

        # Update topic from user input
        if user_input:
            conversation.turn_count += 1
            self._update_topic(session_id, user_input, conversation)

        # Search long-term facts relevant to current input
        long_term_facts = []
        if memory and user_input:
            facts = await memory.search_long_term(user_input, limit=5)
            long_term_facts = [f.content for f in facts]

        snapshot = ContextSnapshot(
            user=user,
            environment=environment,
            conversation=conversation,
            long_term_facts=long_term_facts,
            raw_text=user_input,
        )

        logger.debug(
            "Context snapshot built (topic=%s, emotion=%s, turn=%d)",
            conversation.topic,
            user.current_emotion,
            conversation.turn_count,
        )

        return snapshot

    def update_user_emotion(self, session_id: str, emotion: str) -> None:
        """Update the detected emotion for the current user."""
        user = self._get_user_context(session_id)
        user.current_emotion = emotion

    def update_user_preference(self, session_id: str, key: str, value: Any) -> None:
        """Record a user preference."""
        user = self._get_user_context(session_id)
        user.preferences[key] = value

    def set_topic(self, session_id: str, topic: str, sub_topic: str = "") -> None:
        """Explicitly set the conversation topic."""
        conv = self._get_conversation_context(session_id)
        conv.topic = topic
        conv.sub_topic = sub_topic

    def set_urgency(self, session_id: str, urgency: str) -> None:
        """Set the urgency level for the conversation."""
        conv = self._get_conversation_context(session_id)
        conv.urgency = urgency

    def _get_user_context(self, session_id: str) -> UserContext:
        if session_id not in self._user_contexts:
            self._user_contexts[session_id] = UserContext()
        return self._user_contexts[session_id]

    def _get_conversation_context(self, session_id: str) -> ConversationContext:
        if session_id not in self._conversation_contexts:
            self._conversation_contexts[session_id] = ConversationContext()
        return self._conversation_contexts[session_id]

    def _build_environment_context(self, now: datetime) -> EnvironmentContext:
        """Build environment context from system info and time."""
        hour = now.hour

        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        return EnvironmentContext(
            platform=platform.system(),
            time_of_day=time_of_day,
            hour=hour,
            day_of_week=now.strftime("%A"),
            is_weekend=now.weekday() >= 5,
        )

    def _update_topic(self, session_id: str, user_input: str, conv: ConversationContext) -> None:
        """Extract and update the conversation topic from user input."""
        words = user_input.lower().split()

        # Simple topic extraction from question words
        topic_indicators = {
            "weather": "weather",
            "temperature": "weather",
            "forecast": "weather",
            "email": "email",
            "mail": "email",
            "schedule": "calendar",
            "calendar": "calendar",
            "meeting": "calendar",
            "reminder": "reminders",
            "alarm": "reminders",
            "music": "media",
            "play": "media",
            "search": "web_search",
            "find": "web_search",
            "open": "application_control",
            "launch": "application_control",
            "file": "file_management",
            "document": "file_management",
            "code": "programming",
            "program": "programming",
            "debug": "programming",
            "write": "content_creation",
            "draft": "content_creation",
            "explain": "knowledge",
            "what": "knowledge",
            "how": "knowledge",
            "why": "knowledge",
        }

        for word in words:
            if word in topic_indicators:
                new_topic = topic_indicators[word]
                if conv.topic != new_topic:
                    conv.sub_topic = conv.topic if conv.topic else ""
                    conv.topic = new_topic
                    break

    def reset_session(self, session_id: str) -> None:
        """Reset context for a session."""
        self._conversation_contexts.pop(session_id, None)
        self._topic_history.pop(session_id, None)

    def get_stats(self) -> dict:
        return {
            "tracked_users": len(self._user_contexts),
            "active_sessions": len(self._conversation_contexts),
        }
