"""
Conversation manager for JARVIS memory system.
================================================
Wraps the brain's ShortTermMemory and provides a unified API
for managing conversation context within the memory system.

This manager handles:
    - Per-session message storage
    - Automatic summarization
    - Context window management

Usage:
    manager = ConversationManager(max_messages=50)
    manager.add_message("user", "Hello!")
    summary = manager.get_summary()
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from jarvis.utils.helpers import utc_now

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """A single message in the conversation buffer."""
    role: str
    content: str
    timestamp: str = ""
    token_count: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = utc_now().isoformat()
        if not self.token_count:
            self.token_count = len(self.content) // 4


class ConversationManager:
    """Manages per-session conversation buffers for the memory system.

    Provides a rolling window of recent messages and automatic
    summarization for context injection.

    Example:
        manager = ConversationManager(max_messages=50)
        manager.add_message("user", "What's the weather?")
        manager.add_message("assistant", "It's sunny today.")
        summary = manager.get_summary()
    """

    def __init__(self, max_messages: int = 50, summary_threshold: int = 30, window_size: int = 20):
        """Initialize the conversation manager.

        Args:
            max_messages: Maximum messages to keep in buffer.
            summary_threshold: Trigger summarization after this many messages.
            window_size: Number of recent messages to keep in working window.
        """
        self.max_messages = max_messages
        self.summary_threshold = summary_threshold
        self.window_size = window_size
        self._messages: deque[ConversationMessage] = deque(maxlen=max_messages)
        self._summary: str = ""

    def add_message(self, role: str, content: str, **kwargs) -> ConversationMessage:
        """Add a message to the conversation buffer.

        Args:
            role: Message role (user, assistant, system, tool).
            content: Message content.
            **kwargs: Additional metadata.

        Returns:
            The created ConversationMessage.
        """
        msg = ConversationMessage(
            role=role,
            content=content,
            metadata=kwargs,
        )
        self._messages.append(msg)

        # Auto-summarize if threshold reached
        if len(self._messages) >= self.summary_threshold and not self._summary:
            self._update_summary()

        return msg

    def get_summary(self) -> str:
        """Get a summary of the conversation so far."""
        if not self._summary and len(self._messages) > self.window_size:
            self._update_summary()
        return self._summary

    def get_working_window(self) -> list[ConversationMessage]:
        """Get the most recent messages for context."""
        msgs = list(self._messages)
        return msgs[-self.window_size:] if len(msgs) > self.window_size else msgs

    def get_message_count(self) -> int:
        """Get the total number of messages."""
        return len(self._messages)

    def clear(self) -> None:
        """Clear all messages and summary."""
        self._messages.clear()
        self._summary = ""

    def _update_summary(self) -> None:
        """Create a summary of older messages."""
        msgs = list(self._messages)
        if len(msgs) <= self.window_size:
            return

        older = msgs[: len(msgs) - self.window_size]
        user_msgs = [m.content for m in older if m.role == "user"]
        if user_msgs:
            key_points = user_msgs[-5:]  # last 5 user messages
            self._summary = "Earlier: " + "; ".join(key_points)

    def to_context_string(self) -> str:
        """Format conversation as a context string."""
        parts = []
        for msg in self.get_working_window():
            parts.append(f"{msg.role}: {msg.content}")
        return "\n".join(parts)
