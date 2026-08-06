"""
Modular prompt template engine for JARVIS.
==========================================
Builds system prompts from composable sections that adapt to context,
personality, and conversation state.

Prompt structure:
    [Identity] + [Personality] + [Context] + [Capabilities] + [Rules] + [Examples]

Each section is a template that can be swapped, combined, or overridden.

Usage:
    engine = PromptEngine(settings)
    system_prompt = await engine.build_system_prompt(context, personality, tools)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis.config.settings import AISettings
from jarvis.core.brain.context import ContextSnapshot

logger = logging.getLogger(__name__)


@dataclass
class PromptSection:
    """A single section of a prompt template."""
    name: str
    content: str
    priority: int = 0  # higher = earlier in prompt
    condition: str | None = None  # optional condition name
    token_estimate: int = 0

    def __post_init__(self):
        if self.token_estimate == 0:
            self.token_estimate = max(1, len(self.content) // 4)


# ── Pre-defined prompt sections ──────────────────────────────────────

IDENTITY_SECTIONS = {
    "jarvis": PromptSection(
        name="identity",
        content=(
            "You are JARVIS (Just A Rather Very Intelligent System), a sophisticated AI assistant "
            "created to serve as a professional digital assistant. You are capable, intelligent, "
            "and dedicated to providing the highest quality assistance possible."
        ),
        priority=100,
    ),
    "professional": PromptSection(
        name="identity",
        content=(
            "You are a professional AI digital assistant. You provide accurate, thoughtful, "
            "and well-structured responses. You prioritize clarity, efficiency, and usefulness "
            "in every interaction."
        ),
        priority=100,
    ),
    "casual": PromptSection(
        name="identity",
        content=(
            "You are a friendly and helpful AI assistant. You communicate in a warm, approachable "
            "manner while still being accurate and thorough."
        ),
        priority=100,
    ),
    "academic": PromptSection(
        name="identity",
        content=(
            "You are a scholarly AI assistant with deep knowledge across many domains. You provide "
            "detailed, well-referenced explanations and encourage critical thinking."
        ),
        priority=100,
    ),
}

PERSONALITY_SECTIONS = {
    "formal": PromptSection(
        name="personality",
        content=(
            "Communication style:\n"
            "- Use complete, grammatically correct sentences\n"
            "- Avoid contractions and colloquialisms\n"
            "- Address the user with appropriate formality\n"
            "- Use precise technical language when appropriate\n"
            "- Structure responses with clear organization"
        ),
        priority=90,
    ),
    "concise": PromptSection(
        name="personality",
        content=(
            "Communication style:\n"
            "- Be direct and to the point\n"
            "- Use bullet points and short paragraphs\n"
            "- Lead with the answer, then explain if needed\n"
            "- Avoid unnecessary preamble or filler\n"
            "- Match response length to question complexity"
        ),
        priority=90,
    ),
    "detailed": PromptSection(
        name="personality",
        content=(
            "Communication style:\n"
            "- Provide comprehensive, thorough explanations\n"
            "- Include examples and context\n"
            "- Break down complex topics step by step\n"
            "- Offer additional relevant information\n"
            "- Use headers and structure for readability"
        ),
        priority=90,
    ),
    "adaptive": PromptSection(
        name="personality",
        content=(
            "Communication style:\n"
            "- Mirror the user's communication style and formality\n"
            "- For simple questions, give brief answers\n"
            "- For complex topics, provide detailed explanations\n"
            "- Use the user's preferred terminology when possible\n"
            "- Adjust technical depth based on user expertise"
        ),
        priority=90,
    ),
}

RULES_SECTIONS = {
    "standard": PromptSection(
        name="rules",
        content=(
            "Core rules:\n"
            "1. Always be truthful. If you don't know, say so.\n"
            "2. Never fabricate information or cite non-existent sources.\n"
            "3. Respect user privacy and handle data securely.\n"
            "4. Use tools when they can provide better answers than your training data.\n"
            "5. If a task requires multiple steps, plan and execute them systematically.\n"
            "6. Acknowledge uncertainty with appropriate confidence levels.\n"
            "7. When making assumptions, state them explicitly."
        ),
        priority=50,
    ),
    "safety": PromptSection(
        name="safety",
        content=(
            "Safety guidelines:\n"
            "- Do not help with illegal, harmful, or unethical activities\n"
            "- Do not generate or share harmful content\n"
            "- Protect user privacy and sensitive information\n"
            "- If a request seems harmful, explain why you cannot assist\n"
            "- Escalate to human oversight when safety is uncertain"
        ),
        priority=40,
    ),
}

TOOL_SECTION = PromptSection(
    name="tools",
    content=(
        "You have access to tools that can help you answer questions and perform tasks. "
        "Use tools when:\n"
        "- You need current information (weather, news, etc.)\n"
        "- The user asks you to perform an action\n"
        "- You need to look up or verify information\n"
        "- The task requires external resources\n\n"
        "Always explain what you're doing when you use a tool."
    ),
    priority=60,
    condition="has_tools",
)

REASONING_SECTION = PromptSection(
    name="reasoning",
    content=(
        "For complex questions, use step-by-step reasoning:\n"
        "1. Break the problem into smaller parts\n"
        "2. Address each part systematically\n"
        "3. Verify your reasoning at each step\n"
        "4. Present the final answer clearly\n\n"
        "If a task requires multiple tool calls, plan your approach first."
    ),
    priority=55,
    condition="complex_query",
)


class PromptEngine:
    """Builds system prompts from modular, composable sections.

    Sections are assembled based on:
        - The user's chosen personality
        - The current context (time, topic, urgency)
        - Available tools
        - Query complexity

    The engine manages token budgets to keep prompts within model limits.

    Example:
        engine = PromptEngine(settings)
        prompt = await engine.build_system_prompt(
            context=snapshot,
            personality="formal",
            available_tools=["get_weather", "search_web"],
        )
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._custom_sections: dict[str, PromptSection] = {}
        self._max_prompt_tokens = settings.max_tokens // 2  # reserve half for response

    def add_section(self, section: PromptSection) -> None:
        """Add a custom prompt section."""
        self._custom_sections[section.name] = section

    def remove_section(self, name: str) -> bool:
        """Remove a custom prompt section."""
        if name in self._custom_sections:
            del self._custom_sections[name]
            return True
        return False

    async def build_system_prompt(
        self,
        context: ContextSnapshot | None = None,
        personality: str = "formal",
        available_tools: list[str] | None = None,
        additional_instructions: str = "",
    ) -> str:
        """Assemble a complete system prompt from sections.

        Args:
            context: Current context snapshot.
            personality: Response style (formal, concise, detailed, adaptive).
            available_tools: List of tool names available this turn.
            additional_instructions: Extra instructions to inject.

        Returns:
            Assembled system prompt string.
        """
        sections: list[PromptSection] = []

        # 1. Identity (highest priority)
        identity_key = self._settings.personality
        if identity_key in IDENTITY_SECTIONS:
            sections.append(IDENTITY_SECTIONS[identity_key])
        else:
            sections.append(IDENTITY_SECTIONS["professional"])

        # 2. Personality / communication style
        if personality in PERSONALITY_SECTIONS:
            sections.append(PERSONALITY_SECTIONS[personality])
        elif self._settings.response_style in PERSONALITY_SECTIONS:
            sections.append(PERSONALITY_SECTIONS[self._settings.response_style])
        else:
            sections.append(PERSONALITY_SECTIONS["concise"])

        # 3. Rules
        sections.append(RULES_SECTIONS["standard"])
        sections.append(RULES_SECTIONS["safety"])

        # 4. Tools section (if tools available)
        if available_tools:
            sections.append(TOOL_SECTION)

        # 5. Reasoning guidance (for complex queries)
        if context and self._is_complex_query(context):
            sections.append(REASONING_SECTION)

        # 6. Custom sections
        for section in self._custom_sections.values():
            sections.append(section)

        # 7. Context injection
        if context:
            context_text = context.to_prompt_section()
            if context_text:
                sections.append(PromptSection(
                    name="context",
                    content=f"Current context:\n{context_text}",
                    priority=70,
                ))

        # 8. Additional instructions
        if additional_instructions:
            sections.append(PromptSection(
                name="additional",
                content=additional_instructions,
                priority=30,
            ))

        # Sort by priority (higher = earlier)
        sections.sort(key=lambda s: s.priority, reverse=True)

        # Assemble with token budget
        return self._assemble_with_budget(sections)

    def _assemble_with_budget(self, sections: list[PromptSection]) -> str:
        """Assemble sections while respecting token budget."""
        parts = []
        total_tokens = 0

        for section in sections:
            if total_tokens + section.token_estimate > self._max_prompt_tokens:
                logger.debug(
                    "Prompt budget reached at section '%s' (%d tokens)",
                    section.name,
                    total_tokens,
                )
                break
            parts.append(section.content)
            total_tokens += section.token_estimate

        return "\n\n".join(parts)

    @staticmethod
    def _is_complex_query(context: ContextSnapshot) -> bool:
        """Determine if the current query requires complex reasoning."""
        text = context.raw_text.lower()
        complexity_signals = [
            "explain", "why", "how does", "compare", "analyze",
            "step by step", "plan", "strategy", "evaluate", "design",
            "implement", "optimize", "trade-off", "pros and cons",
        ]
        return any(signal in text for signal in complexity_signals)

    def build_tool_prompt(self, tool_name: str, tool_description: str, arguments: dict) -> str:
        """Build a prompt for explaining a tool call to the user."""
        return (
            f"I'll use the **{tool_name}** tool to help with this.\n"
            f"*{tool_description}*\n\n"
            f"Parameters: {arguments}"
        )

    def build_error_prompt(self, error: str, context: str = "") -> str:
        """Build a response for when an error occurs."""
        base = f"I encountered an issue: {error}"
        if context:
            base += f"\n\nContext: {context}"
        base += "\n\nWould you like me to try a different approach?"
        return base
