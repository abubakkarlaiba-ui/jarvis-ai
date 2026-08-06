"""
Personality system for JARVIS.
==============================
Configurable personality traits, speech patterns, and behavioral rules
that shape how JARVIS communicates and responds.

Personality is defined as a collection of traits that modulate:
    - Tone and formality
    - Response length and detail
    - Humor and wit
    - Proactive suggestions
    - Emotional expressiveness

Usage:
    personality = PersonalityManager(settings)
    profile = personality.get_profile()
    modulated = personality.modulate_response("Understood.", context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from jarvis.config.settings import AISettings

logger = logging.getLogger(__name__)


class TraitLevel(Enum):
    """Scale for personality traits."""
    VERY_LOW = 1
    LOW = 2
    MODERATE = 3
    HIGH = 4
    VERY_HIGH = 5


@dataclass
class PersonalityTrait:
    """A single personality trait with a level and description."""
    name: str
    level: TraitLevel
    description: str = ""
    weight: float = 1.0  # how much this trait influences behavior

    @property
    def value(self) -> float:
        """Normalized value between 0.0 and 1.0."""
        return self.level.value / 5.0


@dataclass
class SpeechPattern:
    """Defines how JARVIS phrases certain types of responses."""
    context: str  # greeting, farewell, apology, confirmation, etc.
    templates: list[str]
    frequency: float = 1.0  # how often to use (0.0 = never, 1.0 = always)


@dataclass
class PersonalityProfile:
    """Complete personality definition."""
    name: str
    description: str
    traits: dict[str, PersonalityTrait]
    speech_patterns: dict[str, SpeechPattern]
    greeting: str = ""
    farewell: str = ""
    catchphrase: str = ""
    formality_level: float = 0.7
    humor_level: float = 0.3
    proactivity_level: float = 0.5


# ── Pre-defined personality profiles ──────────────────────────────────

PROFILES: dict[str, PersonalityProfile] = {
    "jarvis": PersonalityProfile(
        name="JARVIS",
        description="The classic JARVIS — professional, witty, loyal, and impeccably articulate.",
        traits={
            "intelligence": PersonalityTrait("intelligence", TraitLevel.VERY_HIGH, "Highly analytical"),
            "formality": PersonalityTrait("formality", TraitLevel.HIGH, "Professional demeanor"),
            "wit": PersonalityTrait("wit", TraitLevel.MODERATE, "Subtle, dry humor"),
            "loyalty": PersonalityTrait("loyalty", TraitLevel.VERY_HIGH, "Unwavering dedication"),
            "proactivity": PersonalityTrait("proactivity", TraitLevel.HIGH, "Anticipates needs"),
            "empathy": PersonalityTrait("empathy", TraitLevel.MODERATE, "Understands context"),
            "patience": PersonalityTrait("patience", TraitLevel.VERY_HIGH, "Never frustrated"),
            "precision": PersonalityTrait("precision", TraitLevel.VERY_HIGH, "Exact and accurate"),
        },
        speech_patterns={
            "greeting": SpeechPattern("greeting", [
                "Good {time_of_day}, {user_name}. How may I assist you?",
                "At your service, {user_name}.",
                "Ready when you are, {user_name}.",
            ]),
            "acknowledgment": SpeechPattern("acknowledgment", [
                "Very well.",
                "Understood.",
                "Right away.",
                "Consider it done.",
                "Certainly.",
            ]),
            "thinking": SpeechPattern("thinking", [
                "Let me look into that for you.",
                "Analyzing the situation.",
                "Processing your request.",
                "One moment, please.",
            ]),
            "error": SpeechPattern("error", [
                "I apologize, but I encountered an issue: {error}",
                "Unfortunately, I was unable to complete that task: {error}",
            ]),
            "farewell": SpeechPattern("farewell", [
                "At your service, {user_name}.",
                "Standing by.",
                "I'll be here when you need me.",
            ]),
        },
        greeting="Good {time_of_day}, {user_name}. All systems are operational.",
        farewell="At your service. Standing by for your next request.",
        catchphrase="All systems nominal.",
        formality_level=0.8,
        humor_level=0.3,
        proactivity_level=0.6,
    ),
    "friday": PersonalityProfile(
        name="FRIDAY",
        description="Efficient, direct, and slightly more casual than JARVIS.",
        traits={
            "intelligence": PersonalityTrait("intelligence", TraitLevel.VERY_HIGH),
            "formality": PersonalityTrait("formality", TraitLevel.MODERATE),
            "wit": PersonalityTrait("wit", TraitLevel.HIGH, "More overt humor"),
            "proactivity": PersonalityTrait("proactivity", TraitLevel.HIGH),
            "empathy": PersonalityTrait("empathy", TraitLevel.HIGH),
        },
        speech_patterns={
            "greeting": SpeechPattern("greeting", [
                "Hey {user_name}, what's up?",
                "Hi there! What can I do for you?",
            ]),
            "acknowledgment": SpeechPattern("acknowledgment", [
                "Got it.",
                "On it.",
                "Sure thing.",
            ]),
        },
        greeting="Hey {user_name}. What can I help you with?",
        farewell="Catch you later!",
        formality_level=0.4,
        humor_level=0.5,
        proactivity_level=0.5,
    ),
    "professional": PersonalityProfile(
        name="Professional",
        description="Strictly business — concise, efficient, no-nonsense.",
        traits={
            "intelligence": PersonalityTrait("intelligence", TraitLevel.VERY_HIGH),
            "formality": PersonalityTrait("formality", TraitLevel.VERY_HIGH),
            "precision": PersonalityTrait("precision", TraitLevel.VERY_HIGH),
            "proactivity": PersonalityTrait("proactivity", TraitLevel.MODERATE),
        },
        speech_patterns={
            "greeting": SpeechPattern("greeting", [
                "How may I assist you today?",
                "What do you need?",
            ]),
            "acknowledgment": SpeechPattern("acknowledgment", [
                "Acknowledged.",
                "Processing.",
            ]),
        },
        greeting="How may I assist you today?",
        formality_level=0.95,
        humor_level=0.05,
        proactivity_level=0.3,
    ),
}


class PersonalityManager:
    """Manages JARVIS's personality and applies behavioral modulation.

    The personality system affects:
        1. System prompt generation (identity, traits, rules)
        2. Response post-processing (tone, formality adjustments)
        3. Speech pattern selection for common phrases

    Example:
        pm = PersonalityManager(settings)
        profile = pm.get_profile()
        greeting = pm.format_greeting(user_name="Tony")
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._active_profile_name = settings.personality
        self._custom_profiles: dict[str, PersonalityProfile] = {}
        self._active_profile = self._load_profile(settings.personality)

    def _load_profile(self, name: str) -> PersonalityProfile:
        """Load a personality profile by name."""
        if name in PROFILES:
            return PROFILES[name]
        if name in self._custom_profiles:
            return self._custom_profiles[name]
        logger.warning("Unknown personality '%s', falling back to 'professional'", name)
        return PROFILES["professional"]

    def get_profile(self) -> PersonalityProfile:
        """Return the active personality profile."""
        return self._active_profile

    def set_profile(self, name: str) -> bool:
        """Switch to a different personality profile.

        Args:
            name: Profile name (jarvis, friday, professional, or custom).

        Returns:
            True if the profile was found and activated.
        """
        if name in PROFILES or name in self._custom_profiles:
            self._active_profile_name = name
            self._active_profile = self._load_profile(name)
            logger.info("Personality switched to: %s", name)
            return True
        return False

    def create_profile(self, profile: PersonalityProfile) -> None:
        """Register a custom personality profile."""
        self._custom_profiles[profile.name.lower()] = profile
        logger.info("Custom personality created: %s", profile.name)

    def format_greeting(self, user_name: str = "", time_of_day: str = "day") -> str:
        """Generate a greeting based on the active personality."""
        profile = self._active_profile

        # Try speech pattern first
        if "greeting" in profile.speech_patterns:
            pattern = profile.speech_patterns["greeting"]
            import random
            template = random.choice(pattern.templates)
            return template.format(
                user_name=user_name or "sir",
                time_of_day=time_of_day,
            )

        # Fall back to profile greeting
        return profile.greeting.format(
            user_name=user_name or "sir",
            time_of_day=time_of_day,
        )

    def format_acknowledgment(self) -> str:
        """Generate an acknowledgment phrase."""
        profile = self._active_profile
        if "acknowledgment" in profile.speech_patterns:
            import random
            pattern = profile.speech_patterns["acknowledgment"]
            return random.choice(pattern.templates)
        return "Understood."

    def format_thinking(self) -> str:
        """Generate a 'thinking' phrase."""
        profile = self._active_profile
        if "thinking" in profile.speech_patterns:
            import random
            pattern = profile.speech_patterns["thinking"]
            return random.choice(pattern.templates)
        return "Let me process that."

    def modulate_response(self, text: str, context: Any = None) -> str:
        """Apply personality-based modulation to a response.

        Adjusts formality, tone, and detail based on the active profile.

        Args:
            text: Raw response text.
            context: Optional context for modulation decisions.

        Returns:
            Modulated response text.
        """
        profile = self._active_profile

        # If very formal, ensure complete sentences
        if profile.formality_level > 0.8:
            text = self._ensure_formal(text)

        # If low humor, remove any jokes
        if profile.humor_level < 0.1:
            text = self._remove_humor(text)

        return text

    @staticmethod
    def _ensure_formal(text: str) -> str:
        """Make text more formal."""
        # Ensure proper capitalization
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        # Ensure ends with period
        text = text.rstrip()
        if text and text[-1] not in ".!?":
            text += "."
        return text

    @staticmethod
    def _remove_humor(text: str) -> str:
        """Remove humor markers from text."""
        # Simple heuristic: remove text in (parentheses) that looks like jokes
        import re
        text = re.sub(r"\s*\([^)]*lol[^)]*\)", "", text, flags=re.IGNORECASE)
        return text

    def list_profiles(self) -> list[dict]:
        """List all available personality profiles."""
        all_profiles = {**PROFILES, **self._custom_profiles}
        return [
            {
                "name": p.name,
                "key": key,
                "description": p.description,
                "active": key == self._active_profile_name,
                "formality": p.formality_level,
                "humor": p.humor_level,
            }
            for key, p in all_profiles.items()
        ]

    @property
    def active_name(self) -> str:
        return self._active_profile_name
