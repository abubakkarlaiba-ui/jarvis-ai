"""
Context injection engine for JARVIS.
======================================
Automatically injects relevant memories into conversation context
so the LLM has access to user preferences, past facts, project
knowledge, and recent interactions.

The injector assembles a context block that is prepended to the
system prompt, giving the AI full situational awareness.

Usage:
    injector = ContextInjector(settings)
    context_block = await injector.build_context(
        query="What's the weather?",
        session_id="session-1",
        memory_system=memory,
    )
"""

from __future__ import annotations

import logging
from typing import Any

from jarvis.config.settings import MemorySettings, AISettings

logger = logging.getLogger(__name__)


class ContextInjector:
    """Builds context blocks for injection into LLM prompts.

    Assembles relevant memories from all sources into a structured
    context block that gives the LLM awareness of:
        - User preferences
        - Relevant facts
        - Recent conversation summaries
        - Active project context
        - Pending reminders

    Example:
        injector = ContextInjector(settings)
        block = await injector.build_context("code review", "session-1", memory)
        # Prepend to system prompt
    """

    def __init__(self, memory_settings: MemorySettings, ai_settings: AISettings | None = None):
        self._settings = memory_settings
        self._ai_settings = ai_settings
        self._enabled = memory_settings.context_injection_enabled
        self._max_tokens = memory_settings.context_max_tokens

    async def build_context(
        self,
        query: str,
        session_id: str,
        memory_system: Any = None,
    ) -> str:
        """Build a context block for the current query.

        Args:
            query: The user's current message.
            session_id: Current session ID.
            memory_system: The MemorySystem instance.

        Returns:
            Formatted context block string.
        """
        if not self._enabled or not memory_system:
            return ""

        sections: list[str] = []
        token_budget = self._max_tokens

        # 1. User preferences (high value, low token cost)
        if self._settings.context_include_preferences and memory_system.preferences:
            prefs_text = memory_system.preferences.to_context_string()
            if prefs_text:
                sections.append(prefs_text)
                token_budget -= len(prefs_text) // 4

        # 2. Relevant facts (from long-term memory)
        if self._settings.context_include_facts and token_budget > 200:
            try:
                facts = await memory_system.search(query, limit=5)
                if facts:
                    facts_text = "Relevant memories:\n"
                    for f in facts[:3]:
                        facts_text += f"- {f.content[:150]}\n"
                    sections.append(facts_text.strip())
                    token_budget -= len(facts_text) // 4
            except Exception as exc:
                logger.debug("Fact injection failed: %s", exc)

        # 3. Recent conversation context
        if self._settings.context_include_recent and token_budget > 200:
            try:
                recent = await memory_system.get_conversation_context(session_id)
                if recent:
                    sections.append(f"Recent conversation: {recent[:300]}")
                    token_budget -= len(recent) // 4
            except Exception as exc:
                logger.debug("Recent context injection failed: %s", exc)

        # 4. Active project context
        if self._settings.context_include_project and token_budget > 200:
            try:
                projects = await memory_system.projects.list_projects()
                if projects:
                    # Get context for the most recently accessed project
                    most_recent = projects[0]
                    proj_ctx = await memory_system.projects.get_project_context(most_recent["name"])
                    if proj_ctx:
                        sections.append(proj_ctx[:400])
            except Exception as exc:
                logger.debug("Project context injection failed: %s", exc)

        # 5. Pending reminders
        if memory_system.reminders and token_budget > 100:
            try:
                due = await memory_system.reminders.get_due()
                if due:
                    reminder_text = "Pending reminders:\n"
                    for r in due[:3]:
                        reminder_text += f"- {r.title}\n"
                    sections.append(reminder_text.strip())
            except Exception as exc:
                logger.debug("Reminder injection failed: %s", exc)

        if not sections:
            return ""

        context_block = "\n\n".join(sections)

        # Enforce token budget
        estimated_tokens = len(context_block) // 4
        if estimated_tokens > self._max_tokens:
            context_block = context_block[:self._max_tokens * 4]

        logger.debug("Context injected: ~%d tokens from %d sections", len(context_block) // 4, len(sections))
        return context_block

    def format_for_prompt(self, context_block: str) -> str:
        """Wrap the context block for inclusion in a system prompt."""
        if not context_block:
            return ""
        return (
            "=== JARVIS MEMORY CONTEXT ===\n"
            f"{context_block}\n"
            "=== END CONTEXT ===\n\n"
            "Use this context to inform your response. "
            "Reference relevant information naturally without explicitly mentioning the context system."
        )
