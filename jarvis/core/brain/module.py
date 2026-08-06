"""
Brain module — the central reasoning engine of JARVIS.
=====================================================
Orchestrates intent recognition, dialogue management, and response generation.

Architecture:
    IntentParser  →  ContextManager  →  ResponseGenerator
         ↑                  ↑                    ↑
    NLP models        conversation state    templates / LLM

Usage:
    brain = BrainModule(settings)
    response = await brain.process("What's the weather in London?")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Supported intent categories for user commands."""
    GREETING = auto()
    QUESTION = auto()
    COMMAND = auto()
    SYSTEM_CONTROL = auto()
    MEMORY_QUERY = auto()
    UNKNOWN = auto()


@dataclass
class ParsedIntent:
    """Structured representation of a recognized intent."""
    intent: Intent
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainResponse:
    """Response produced by the Brain module."""
    text: str
    intent: Intent
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    requires_action: bool = False
    action_data: dict[str, Any] | None = None


class IntentParser:
    """Parses raw user text into structured intents.

    Uses a combination of keyword matching and optional LLM-based parsing.
    Designed to be extended with custom intent classifiers.
    """

    INTENT_KEYWORDS: dict[Intent, list[str]] = {
        Intent.GREETING: ["hello", "hi", "hey", "good morning", "good evening"],
        Intent.SYSTEM_CONTROL: [
            "shutdown", "restart", "sleep", "wake", "volume", "brightness",
        ],
        Intent.MEMORY_QUERY: ["remember", "recall", "what did", "last time"],
    }

    def parse(self, text: str) -> ParsedIntent:
        """Parse raw text into a ParsedIntent.

        Args:
            text: The raw user input string.

        Returns:
            A ParsedIntent with the best-matching intent and confidence.
        """
        normalized = text.lower().strip()

        best_intent = Intent.UNKNOWN
        best_confidence = 0.0

        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in normalized:
                    confidence = min(1.0, len(keyword) / len(normalized) + 0.3)
                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence

        if best_intent == Intent.UNKNOWN:
            best_confidence = 0.2

        return ParsedIntent(
            intent=best_intent,
            confidence=best_confidence,
            raw_text=text,
        )


class ContextManager:
    """Manages conversational context and history.

    Tracks the current dialogue state, recent intents, and extracted entities
    to enable context-aware responses.
    """

    def __init__(self, max_history: int = 20):
        self.history: list[dict[str, Any]] = []
        self.current_topic: str | None = None
        self.max_history = max_history

    def add_exchange(self, user_text: str, intent: ParsedIntent, response: str) -> None:
        """Record a user-assistant exchange in the conversation history.

        Args:
            user_text: What the user said.
            intent: The parsed intent of the user's message.
            response: The assistant's response text.
        """
        self.history.append({
            "user": user_text,
            "intent": intent.intent.name,
            "response": response,
        })
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_recent_context(self, n: int = 5) -> list[dict[str, Any]]:
        """Return the last n exchanges from conversation history."""
        return self.history[-n:]

    def clear(self) -> None:
        """Reset conversation history."""
        self.history.clear()
        self.current_topic = None


class ResponseGenerator:
    """Generates responses based on intents and context.

    Template-based responses for simple intents, with hooks for LLM generation.
    """

    TEMPLATES: dict[Intent, list[str]] = {
        Intent.GREETING: [
            "Hello! How can I help you today?",
            "Hi there! What can I do for you?",
            "Good to see you! How may I assist?",
        ],
        Intent.QUESTION: [
            "Let me look into that for you.",
            "I'm searching for information on that topic.",
        ],
        Intent.COMMAND: [
            "Executing your command now.",
            "Right away, processing your request.",
        ],
        Intent.SYSTEM_CONTROL: [
            "Adjusting system settings.",
            "System control action initiated.",
        ],
        Intent.MEMORY_QUERY: [
            "Let me check my memory for that.",
            "Searching through my records.",
        ],
        Intent.UNKNOWN: [
            "I'm not sure I understand. Could you rephrase that?",
            "I didn't quite catch that. Can you say it differently?",
        ],
    }

    def generate(self, intent: ParsedIntent, context: list[dict[str, Any]] | None = None) -> str:
        """Generate a response text for the given intent.

        Args:
            intent: The parsed intent from user input.
            context: Optional recent conversation context.

        Returns:
            A response string.
        """
        import random
        templates = self.TEMPLATES.get(intent.intent, self.TEMPLATES[Intent.UNKNOWN])
        return random.choice(templates)


class BrainModule:
    """Central brain orchestrator.

    Coordinates intent parsing, context management, and response generation
    into a single processing pipeline.

    Example:
        brain = BrainModule()
        response = await brain.process("Set an alarm for 7am")
    """

    def __init__(self):
        self.intent_parser = IntentParser()
        self.context_manager = ContextManager()
        self.response_generator = ResponseGenerator()
        logger.info("BrainModule initialized")

    async def process(self, user_input: str) -> BrainResponse:
        """Process a user input string through the full brain pipeline.

        Args:
            user_input: Raw text from the user.

        Returns:
            A BrainResponse with the generated reply and metadata.
        """
        logger.info("Processing input: %s", user_input[:100])

        intent = self.intent_parser.parse(user_input)
        context = self.context_manager.get_recent_context()

        response_text = self.response_generator.generate(intent, context)

        self.context_manager.add_exchange(user_input, intent, response_text)

        return BrainResponse(
            text=response_text,
            intent=intent.intent,
            confidence=intent.confidence,
            metadata={"entities": intent.entities},
            requires_action=intent.intent in (Intent.COMMAND, Intent.SYSTEM_CONTROL),
            action_data=intent.parameters,
        )
