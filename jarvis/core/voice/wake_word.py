"""
Wake word detection for JARVIS.
================================
Detects the "Hey Jarvis" wake word to activate the assistant.

Uses a lightweight approach:
    1. Run VAD to detect speech segments
    2. Transcribe the speech segment with Whisper (fast, small window)
    3. Check if the transcription matches the wake word pattern

This avoids the need for a separate wake-word model and gives
flexibility in wake word phrases.

Alternative: pvporcupine or custom ONNX model for always-on detection.

Usage:
    detector = WakeWordDetector(settings)
    await detector.initialize()
    async for audio in mic.stream():
        if await detector.check(audio):
            print("Wake word detected!")
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

from jarvis.config.settings import VoiceSettings

logger = logging.getLogger(__name__)


@dataclass
class WakeWordConfig:
    """Wake word detection configuration."""
    phrase: str = "hey jarvis"
    sensitivity: float = 0.5
    sample_rate: int = 16000
    min_speech_ms: int = 300
    max_speech_ms: int = 3000
    cooldown_ms: int = 2000


class PatternMatcher:
    """Fuzzy text matching for wake word detection.

    Uses multiple strategies to match the wake word against
    transcribed text, handling common misrecognitions.
    """

    # Common Whisper misrecognitions of "hey jarvis"
    ALTERNATIVES = [
        "hey jarvis",
        "hey jars",
        "hey jars is",
        "hey jarvs",
        "hey jarvis's",
        "hey jar v is",
        "hey j",
        "hey jar",
        "hey jervis",
        "hey gervis",
        "hey gerivs",
        "hey jarvis",
    ]

    def __init__(self, phrase: str):
        self.phrase = phrase.lower().strip()
        self._pattern = self._build_pattern(phrase)

    def _build_pattern(self, phrase: str) -> re.Pattern:
        """Build a regex pattern for flexible matching."""
        words = phrase.lower().split()
        # Allow some character variation between words
        flexible = r"\s+".join(re.escape(w) for w in words)
        return re.compile(flexible, re.IGNORECASE)

    def match(self, text: str) -> tuple[bool, float]:
        """Check if text contains the wake word.

        Args:
            text: Transcribed text to check.

        Returns:
            Tuple of (is_match, confidence).
        """
        if not text:
            return False, 0.0

        normalized = text.lower().strip()

        # Exact match
        if self.phrase in normalized:
            return True, 1.0

        # Regex pattern match
        if self._pattern.search(normalized):
            return True, 0.9

        # Fuzzy match against known alternatives
        for alt in self.ALTERNATIVES:
            if alt in normalized:
                return True, 0.7

        # Levenshtein-style: check if phrase words appear in sequence
        phrase_words = self.phrase.split()
        text_words = normalized.split()
        if len(text_words) <= len(phrase_words) + 2:
            matches = 0
            pi = 0
            for tw in text_words:
                if pi < len(phrase_words) and self._word_similar(tw, phrase_words[pi]):
                    matches += 1
                    pi += 1
            if pi == len(phrase_words):
                confidence = matches / len(phrase_words) * 0.8
                return True, confidence

        return False, 0.0

    @staticmethod
    def _word_similar(a: str, b: str) -> bool:
        """Check if two words are similar enough (simple edit distance)."""
        if a == b:
            return True
        if len(a) < 2 or len(b) < 2:
            return False
        # Allow 1 character difference for short words, 2 for longer
        max_diff = 1 if len(a) <= 4 else 2
        diff = sum(1 for ca, cb in zip(a, b) if ca != cb) + abs(len(a) - len(b))
        return diff <= max_diff


class WakeWordDetector:
    """Detects the wake word to activate JARVIS.

    Operates in two modes:
        - Passive: monitors VAD output, transcribes speech segments,
          checks for wake word match
        - Active (after detection): hands off to the main pipeline

    The detector maintains a rolling buffer of recent audio and
    only transcribes when VAD indicates speech, keeping CPU usage low.

    Usage:
        detector = WakeWordDetector(settings, vad, stt)
        await detector.initialize()
        async for frame in mic.stream():
            if await detector.process_frame(frame):
                # Wake word detected — start command listening
                pass
    """

    def __init__(
        self,
        settings: VoiceSettings,
        vad=None,
        stt=None,
    ):
        self._config = WakeWordConfig(
            phrase=settings.wake_word,
            sensitivity=settings.wake_word_sensitivity,
            sample_rate=settings.mic_sample_rate,
            min_speech_ms=settings.vad_speech_duration_ms,
            max_speech_ms=settings.max_record_seconds * 1000,
        )
        self._vad = vad
        self._stt = stt
        self._matcher = PatternMatcher(settings.wake_word)

        # Audio buffer for accumulating speech segments
        self._speech_buffer: list[np.ndarray] = []
        self._is_listening_for_wake = True
        self._last_detection_time = 0.0
        self._cooldown_seconds = self._config.cooldown_ms / 1000.0

        # Stats
        self._checks = 0
        self._detections = 0

        logger.info("WakeWordDetector created (phrase='%s')", settings.wake_word)

    async def initialize(self) -> None:
        """Initialize the wake word detector."""
        if self._vad:
            self._vad.initialize()
        logger.info("WakeWordDetector initialized")

    async def process_frame(self, audio_float32: np.ndarray) -> bool:
        """Process a single audio frame and check for wake word.

        This method should be called for every audio frame from the
        microphone. It accumulates speech segments via VAD and
        transcribes them for wake word matching.

        Args:
            audio_float32: Float32 audio samples (one VAD window).

        Returns:
            True if the wake word was detected.
        """
        if not self._is_listening_for_wake:
            return False

        # Rate limiting: enforce cooldown between detections
        now = time.monotonic()
        if now - self._last_detection_time < self._cooldown_seconds:
            return False

        # Check VAD if available
        if self._vad:
            is_speech = self._vad.is_speech(audio_float32)
            if not is_speech:
                # If we had accumulated speech, check it
                if self._speech_buffer:
                    detected = await self._check_accumulated_speech()
                    self._speech_buffer.clear()
                    if detected:
                        return True
                return False

        # Accumulate speech audio
        self._speech_buffer.append(audio_float32)

        # Check if buffer is getting too long (max speech duration)
        total_samples = sum(len(chunk) for chunk in self._speech_buffer)
        max_samples = int(self._config.max_speech_ms / 1000 * self._config.sample_rate)

        if total_samples >= max_samples:
            # Buffer too long — check and clear
            detected = await self._check_accumulated_speech()
            self._speech_buffer.clear()
            if detected:
                return True

        return False

    async def _check_accumulated_speech(self) -> bool:
        """Transcribe accumulated speech and check for wake word."""
        if not self._speech_buffer or not self._stt:
            return False

        # Check minimum duration
        total_samples = sum(len(c) for c in self._speech_buffer)
        duration_ms = total_samples / self._config.sample_rate * 1000
        if duration_ms < self._config.min_speech_ms:
            return False

        self._checks += 1

        # Concatenate and transcribe
        combined = np.concatenate(self._speech_buffer)
        text = await self._stt.transcribe(combined, self._config.sample_rate)

        if not text:
            return False

        # Check for wake word
        is_match, confidence = self._matcher.match(text)

        if is_match and confidence >= self._config.sensitivity:
            self._last_detection_time = time.monotonic()
            self._detections += 1
            logger.info(
                "Wake word detected! (text='%s', confidence=%.2f)", text, confidence
            )
            return True

        if text.strip():
            logger.debug("Wake word check: '%s' (no match)", text[:40])

        return False

    def check_text(self, text: str) -> bool:
        """Directly check a text string for the wake word.

        Useful for testing or when audio is pre-transcribed.

        Args:
            text: Text to check.

        Returns:
            True if the wake word is found.
        """
        is_match, confidence = self._matcher.match(text)
        if is_match:
            self._detections += 1
            self._last_detection_time = time.monotonic()
        return is_match

    def set_listening(self, listening: bool) -> None:
        """Enable or disable wake word listening."""
        self._is_listening_for_wake = listening

    def reset(self) -> None:
        """Reset detector state for a new session."""
        self._speech_buffer.clear()
        self._last_detection_time = 0.0

    @property
    def stats(self) -> dict:
        return {
            "phrase": self._config.phrase,
            "checks": self._checks,
            "detections": self._detections,
            "listening": self._is_listening_for_wake,
            "buffer_samples": sum(len(c) for c in self._speech_buffer),
        }
