"""
Conversation summarizer for JARVIS.
====================================
Automatically summarizes conversation history when it grows too long,
preserving key information while reducing context length.

Summarization strategies:
    - Extractive: picks the most important sentences
    - Progressive: incremental summarization as conversation grows
    - Thematic: groups by topic and summarizes each theme

Usage:
    summarizer = ConversationSummarizer(settings)
    summary = await summarizer.summarize(messages)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from jarvis.config.settings import AISettings

logger = logging.getLogger(__name__)


@dataclass
class ConversationSummary:
    """A summary of a conversation segment."""
    text: str
    key_points: list[str]
    topics: list[str]
    entities_mentioned: dict[str, str]
    message_range: tuple[int, int]  # start and end message indices
    token_count: int = 0

    def to_context_string(self) -> str:
        """Convert to a string suitable for context injection."""
        parts = [f"Previous conversation summary: {self.text}"]
        if self.key_points:
            parts.append("Key points discussed:")
            for point in self.key_points[:5]:
                parts.append(f"  - {point}")
        if self.topics:
            parts.append(f"Topics: {', '.join(self.topics)}")
        return "\n".join(parts)


class ConversationSummarizer:
    """Summarizes conversation history to manage context length.

    When the conversation grows beyond a threshold, the summarizer
    condenses older messages into a summary that preserves the most
    important information.

    Example:
        summarizer = ConversationSummarizer(settings)
        summary = await summarizer.summarize(messages)
        # Use summary to replace older messages in context
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._enabled = settings.summarization_enabled
        self._threshold = settings.summarization_threshold

    async def summarize(self, messages: list[dict[str, Any]]) -> ConversationSummary:
        """Summarize a list of conversation messages.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            ConversationSummary with extracted key information.
        """
        if not self._enabled or not messages:
            return ConversationSummary(
                text="",
                key_points=[],
                topics=[],
                entities_mentioned={},
                message_range=(0, 0),
            )

        # Extract user and assistant messages
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        assistant_msgs = [m["content"] for m in messages if m.get("role") == "assistant"]

        # Build extractive summary
        key_points = self._extract_key_points(messages)
        topics = self._extract_topics(messages)
        entities = self._extract_entities(messages)

        # Generate summary text
        summary_text = self._generate_summary_text(key_points, topics, len(messages))

        return ConversationSummary(
            text=summary_text,
            key_points=key_points,
            topics=topics,
            entities_mentioned=entities,
            message_range=(0, len(messages) - 1),
            token_count=len(summary_text) // 4,
        )

    def _extract_key_points(self, messages: list[dict[str, Any]]) -> list[str]:
        """Extract the most important points from messages."""
        key_points = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            # Skip very short messages
            if len(content) < 10:
                continue

            # User questions are usually important
            if role == "user" and ("?" in content or any(w in content.lower() for w in [
                "what", "how", "why", "when", "where", "can you", "help",
                "need", "want", "please", "important",
            ])):
                key_points.append(content[:200])

            # Assistant conclusions
            if role == "assistant" and any(w in content.lower() for w in [
                "the answer is", "in summary", "to summarize",
                "the key point", "importantly", "the solution",
            ]):
                key_points.append(content[:200])

        return key_points[:10]  # limit to top 10

    def _extract_topics(self, messages: list[dict[str, Any]]) -> list[str]:
        """Identify main topics discussed."""
        topic_keywords = {
            "programming": ["code", "program", "function", "debug", "error", "python", "javascript"],
            "weather": ["weather", "temperature", "forecast", "rain", "sunny"],
            "email": ["email", "mail", "inbox", "send", "message"],
            "calendar": ["meeting", "schedule", "calendar", "appointment", "event"],
            "research": ["research", "study", "find", "search", "information"],
            "file_management": ["file", "folder", "save", "document", "directory"],
            "system": ["system", "computer", "cpu", "memory", "disk", "process"],
        }

        all_text = " ".join(m.get("content", "").lower() for m in messages)
        detected_topics = []

        for topic, keywords in topic_keywords.items():
            if any(kw in all_text for kw in keywords):
                detected_topics.append(topic)

        return detected_topics[:5]

    def _extract_entities(self, messages: list[dict[str, Any]]) -> dict[str, str]:
        """Extract named entities from messages."""
        entities = {}

        # Simple entity extraction patterns
        import re

        for msg in messages:
            content = msg.get("content", "")

            # Look for "my name is X" patterns
            name_match = re.search(r"my name is (\w+)", content, re.IGNORECASE)
            if name_match:
                entities["user_name"] = name_match.group(1)

            # Look for file paths
            file_match = re.search(r"[/\\][\w./\\]+\.\w+", content)
            if file_match:
                entities["file_mentioned"] = file_match.group(0)

            # Look for dates
            date_match = re.search(
                r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2},? \d{4}",
                content,
            )
            if date_match:
                entities["date_mentioned"] = date_match.group(0)

        return entities

    def _generate_summary_text(
        self,
        key_points: list[str],
        topics: list[str],
        message_count: int,
    ) -> str:
        """Generate human-readable summary text."""
        parts = [f"Conversation covering {message_count} messages"]

        if topics:
            parts.append(f"Topics: {', '.join(topics)}")

        if key_points:
            parts.append("Key points:")
            for point in key_points[:3]:
                parts.append(f"  - {point[:100]}")

        return ". ".join(parts) + "."

    def should_summarize(self, message_count: int) -> bool:
        """Check if the conversation should be summarized."""
        return self._enabled and message_count >= self._threshold
