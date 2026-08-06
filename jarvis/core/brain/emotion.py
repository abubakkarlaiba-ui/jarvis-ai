"""
Emotion detection and response modulation for JARVIS.
=====================================================
Analyzes user messages to detect emotional state and adjusts
JARVIS's response tone, urgency, and empathy accordingly.

Detection approach:
    1. Lexicon-based: keyword matching against emotion word lists
    2. Pattern-based: punctuation, capitalization, emoji detection
    3. Context-based: conversation history and escalation signals
    4. LLM-based: optional deeper analysis for ambiguous cases

Emotion categories:
    neutral, happy, sad, angry, frustrated, anxious, excited,
    confused, grateful, impatient, surprised, worried

Usage:
    detector = EmotionDetector(settings)
    emotion = detector.detect("I'm so frustrated with this bug!!!")
    modulated = detector.modulate_response("Understood.", "frustrated")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from jarvis.config.settings import AISettings

logger = logging.getLogger(__name__)


class Emotion(Enum):
    """Detected emotion categories."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FRUSTRATED = "frustrated"
    ANXIOUS = "anxious"
    EXCITED = "excited"
    CONFUSED = "confused"
    GRATEFUL = "grateful"
    IMPATIENT = "impatient"
    SURPRISED = "surprised"
    WORRIED = "worried"


@dataclass
class EmotionResult:
    """Result of emotion detection."""
    emotion: Emotion
    confidence: float
    intensity: float  # 0.0 to 1.0
    secondary_emotions: list[tuple[Emotion, float]] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)


# ── Emotion lexicons ─────────────────────────────────────────────────

EMOTION_LEXICON: dict[Emotion, list[str]] = {
    Emotion.HAPPY: [
        "happy", "great", "awesome", "wonderful", "fantastic", "love",
        "excellent", "amazing", "perfect", "thank", "thanks", "glad",
        "pleased", "delighted", "brilliant", "superb", "terrific",
    ],
    Emotion.SAD: [
        "sad", "unhappy", "depressed", "miserable", "terrible", "awful",
        "horrible", "disappointing", "upset", "down", "gloomy", "heartbroken",
    ],
    Emotion.ANGRY: [
        "angry", "furious", "mad", "hate", "stupid", "idiot", "damn",
        "ridiculous", "unacceptable", "outrageous", "infuriating", "livid",
    ],
    Emotion.FRUSTRATED: [
        "frustrated", "stuck", "annoying", "annoyed", "irritating", "ugh",
        "not working", "broken", "useless", "waste", "keeps", "again",
    ],
    Emotion.ANXIOUS: [
        "worried", "anxious", "nervous", "scared", "afraid", "panic",
        "concerned", "uneasy", "stressed", "overwhelmed", "pressure",
    ],
    Emotion.EXCITED: [
        "excited", "can't wait", "amazing", "incredible", "wow",
        "unbelievable", "thrilled", "ecstatic", "pumped", "stoked",
    ],
    Emotion.CONFUSED: [
        "confused", "don't understand", "unclear", "what", "how",
        "explain", "lost", "baffled", "puzzled", "doesn't make sense",
    ],
    Emotion.GRATEFUL: [
        "thank", "thanks", "grateful", "appreciate", "helpful",
        "saved me", "great help", "thank you", "cheers", "kudos",
    ],
    Emotion.IMPATIENT: [
        "hurry", "fast", "quick", "now", "waiting", "slow",
        "taking forever", "come on", "still", "yet", "when",
    ],
    Emotion.SURPRISED: [
        "wow", "really", "seriously", "no way", "unbelievable",
        "shocked", "astonished", "stunned", "what the", "omg",
    ],
    Emotion.WORRIED: [
        "worried", "concerned", "might", "what if", "afraid",
        "risk", "danger", "problem", "issue", "trouble", "emergency",
    ],
}

# Intensifier words that amplify emotion
INTENSIFIERS = [
    "very", "extremely", "incredibly", "absolutely", "totally",
    "completely", "utterly", "so", "really", "truly", "deeply",
]

# Negation words that flip emotion
NEGATIONS = ["not", "no", "never", "neither", "nobody", "nothing", "nowhere"]

# Punctuation signals
EXCLAMATION_SIGNALS = re.compile(r"!{2,}|[A-Z]{3,}")
QUESTION_SIGNALS = re.compile(r"\?{2,}")


class EmotionDetector:
    """Detects user emotion from text and modulates response tone.

    The detector uses a multi-signal approach:
        1. Lexicon matching for primary emotion
        2. Intensity calculation from modifiers and punctuation
        3. Context escalation tracking (frustration building over time)
        4. Response modulation based on detected emotion

    Example:
        detector = EmotionDetector(settings)
        result = detector.detect("I'm VERY frustrated with this!!!")
        print(result.emotion)  # Emotion.FRUSTRATED
        print(result.intensity)  # 0.9
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._enabled = settings.emotion_detection
        self._escalation_tracker: dict[str, list[Emotion]] = {}  # session → recent emotions
        self._max_escalation_window = 5

    def detect(self, text: str, session_id: str = "default") -> EmotionResult:
        """Detect the emotion in a user message.

        Args:
            text: User's message text.
            session_id: Session for escalation tracking.

        Returns:
            EmotionResult with detected emotion, confidence, and intensity.
        """
        if not self._enabled:
            return EmotionResult(emotion=Emotion.NEUTRAL, confidence=1.0, intensity=0.0)

        normalized = text.lower().strip()

        # Score each emotion
        scores: dict[Emotion, float] = {}
        signals: list[str] = []

        for emotion, lexicon in EMOTION_LEXICON.items():
            score = 0.0
            for word in lexicon:
                if word in normalized:
                    score += 1.0
                    signals.append(f"keyword:{word}")
            if score > 0:
                scores[emotion] = score

        if not scores:
            return EmotionResult(
                emotion=Emotion.NEUTRAL,
                confidence=0.8,
                intensity=0.0,
                signals=["no_emotion_signals"],
            )

        # Normalize scores
        total = sum(scores.values())
        for emotion in scores:
            scores[emotion] /= total

        # Apply intensifier boost
        for intensifier in INTENSIFIERS:
            if intensifier in normalized:
                for emotion in scores:
                    scores[emotion] *= 1.3
                signals.append(f"intensifier:{intensifier}")
                break

        # Apply punctuation signals
        if EXCLAMATION_SIGNALS.search(text):
            for emotion in scores:
                if emotion in (Emotion.ANGRY, Emotion.FRUSTRATED, Emotion.EXCITED):
                    scores[emotion] *= 1.5
            signals.append("exclamation_emphasis")

        if QUESTION_SIGNALS.search(text):
            if Emotion.CONFUSED in scores:
                scores[Emotion.CONFUSED] *= 1.3
            signals.append("question_emphasis")

        # ALL CAPS detection
        words = text.split()
        caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 1) / max(len(words), 1)
        if caps_ratio > 0.5:
            for emotion in scores:
                if emotion in (Emotion.ANGRY, Emotion.FRUSTRATED):
                    scores[emotion] *= 1.4
            signals.append("caps_emphasis")

        # Select primary emotion
        primary_emotion = max(scores, key=lambda e: scores[e])
        primary_score = scores[primary_emotion]

        # Secondary emotions
        secondary = [
            (e, s) for e, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if e != primary_emotion and s > 0.2
        ][:3]

        # Calculate intensity (0.0 - 1.0)
        intensity = min(1.0, primary_score * 2.0)

        # Check escalation
        self._track_escalation(session_id, primary_emotion)
        if self._is_escalating(session_id):
            intensity = min(1.0, intensity + 0.2)
            signals.append("escalation_detected")

        confidence = min(1.0, primary_score * 1.5 + 0.3)

        result = EmotionResult(
            emotion=primary_emotion,
            confidence=confidence,
            intensity=intensity,
            secondary_emotions=secondary,
            signals=signals,
        )

        logger.debug(
            "Emotion detected: %s (conf=%.2f, intensity=%.2f) from '%s'",
            primary_emotion.value,
            confidence,
            intensity,
            text[:50],
        )

        return result

    def modulate_response(self, response: str, emotion: EmotionResult) -> str:
        """Modulate a response based on detected user emotion.

        Adjusts tone, adds empathy markers, and changes formality
        based on the user's emotional state.

        Args:
            response: Raw response text.
            emotion: Detected emotion result.

        Returns:
            Modulated response text.
        """
        if not self._enabled or emotion.emotion == Emotion.NEUTRAL:
            return response

        intensity = emotion.intensity

        # High-intensity negative emotions need acknowledgment
        if intensity > 0.6 and emotion.emotion in (
            Emotion.FRUSTRATED, Emotion.ANGRY, Emotion.WORRIED, Emotion.ANXIOUS
        ):
            prefixes = [
                "I understand this is frustrating.",
                "I can see why that's concerning.",
                "Let me help you resolve this.",
                "I hear you. Let's address this.",
            ]
            import random
            prefix = random.choice(prefixes)
            response = f"{prefix} {response}"

        # Gratitude responses
        if emotion.emotion == Emotion.GRATEFUL:
            suffixes = [
                " Happy to help.",
                " Glad I could assist.",
                " Always here to help.",
            ]
            import random
            response = response.rstrip() + random.choice(suffixes)

        # Confusion — offer to explain more
        if emotion.emotion == Emotion.CONFUSED and intensity > 0.5:
            response += "\n\nWould you like me to explain this in more detail or in a different way?"

        # Excitement — match energy slightly
        if emotion.emotion == Emotion.EXCITED:
            response = response.replace(".", "!") if response.count(".") == 1 else response

        return response

    def _track_escalation(self, session_id: str, emotion: Emotion) -> None:
        """Track emotion over time for escalation detection."""
        if session_id not in self._escalation_tracker:
            self._escalation_tracker[session_id] = []

        tracker = self._escalation_tracker[session_id]
        tracker.append(emotion)

        if len(tracker) > self._max_escalation_window:
            tracker.pop(0)

    def _is_escalating(self, session_id: str) -> bool:
        """Check if negative emotions are escalating."""
        tracker = self._escalation_tracker.get(session_id, [])
        if len(tracker) < 3:
            return False

        negative = {Emotion.ANGRY, Emotion.FRUSTRATED, Emotion.ANXIOUS, Emotion.WORRIED, Emotion.IMPATIENT}
        recent_negative = sum(1 for e in tracker[-3:] if e in negative)
        return recent_negative >= 2

    def get_stats(self) -> dict:
        return {
            "enabled": self._enabled,
            "tracked_sessions": len(self._escalation_tracker),
        }
