"""
Voice module — speech-to-text, text-to-speech, and wake-word detection.
======================================================================
Provides an async voice pipeline for natural interaction with JARVIS.

Architecture:
    WakeWordDetector  →  SpeechToText  →  TextToSpeech
         ↑                    ↑                 ↑
    audio stream         audio input        text output

Usage:
    voice = VoiceModule(settings)
    text = await voice.listen()
    await voice.speak("Hello, sir.")
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class VoiceState(Enum):
    """Current state of the voice subsystem."""
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()


@dataclass
class AudioChunk:
    """A chunk of audio data with metadata."""
    data: bytes
    sample_rate: int
    channels: int = 1
    duration_ms: float = 0.0
    timestamp: float = 0.0


class SpeechToText(ABC):
    """Abstract base class for speech-to-text engines."""

    @abstractmethod
    async def transcribe(self, audio: AudioChunk) -> str:
        """Transcribe an audio chunk to text.

        Args:
            audio: AudioChunk containing raw audio data.

        Returns:
            Transcribed text string.
        """
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the STT engine and load models."""
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Release resources held by the STT engine."""
        ...


class TextToSpeech(ABC):
    """Abstract base class for text-to-speech engines."""

    @abstractmethod
    async def synthesize(self, text: str) -> AudioChunk:
        """Convert text to audio.

        Args:
            text: The text to synthesize.

        Returns:
            An AudioChunk with the generated audio.
        """
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the TTS engine and load models."""
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Release resources held by the TTS engine."""
        ...


class WakeWordDetector(ABC):
    """Abstract base class for wake-word detection."""

    @abstractmethod
    async def detect(self, audio: AsyncIterator[AudioChunk]) -> bool:
        """Listen for the wake word in a stream of audio chunks.

        Args:
            audio: Async iterator of incoming audio chunks.

        Returns:
            True when the wake word is detected.
        """
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the wake-word model."""
        ...


class DummySpeechToText(SpeechToText):
    """Placeholder STT engine for development and testing."""

    async def initialize(self) -> None:
        logger.info("DummySpeechToText initialized (no-op)")

    async def transcribe(self, audio: AudioChunk) -> str:
        logger.debug("DummySpeechToText: returning placeholder transcription")
        return "dummy transcription"

    async def cleanup(self) -> None:
        pass


class DummyTextToSpeech(TextToSpeech):
    """Placeholder TTS engine for development and testing."""

    async def initialize(self) -> None:
        logger.info("DummyTextToSpeech initialized (no-op)")

    async def synthesize(self, text: str) -> AudioChunk:
        logger.debug("DummyTextToSpeech: returning placeholder audio for '%s'", text[:50])
        return AudioChunk(data=b"", sample_rate=16000)

    async def cleanup(self) -> None:
        pass


class VoiceModule:
    """High-level voice orchestrator.

    Coordinates wake-word detection, STT, and TTS into a unified interface.
    Engines are pluggable — pass custom implementations via the constructor.

    Example:
        voice = VoiceModule(settings)
        await voice.initialize()
        text = await voice.listen()
        await voice.speak("Processing your request.")
        await voice.cleanup()
    """

    def __init__(
        self,
        stt: SpeechToText | None = None,
        tts: TextToSpeech | None = None,
        wake_word: WakeWordDetector | None = None,
    ):
        self.stt = stt or DummySpeechToText()
        self.tts = tts or DummyTextToSpeech()
        self.wake_word = wake_word
        self.state = VoiceState.IDLE
        logger.info("VoiceModule created")

    async def initialize(self) -> None:
        """Initialize all voice subsystems."""
        await self.stt.initialize()
        await self.tts.initialize()
        if self.wake_word:
            await self.wake_word.initialize()
        logger.info("VoiceModule initialized")

    async def listen(self) -> str:
        """Listen for speech and return transcribed text.

        Returns:
            The transcribed text from the user's speech.
        """
        self.state = VoiceState.LISTENING
        logger.debug("VoiceModule: listening...")
        # In production, capture audio from microphone here
        chunk = AudioChunk(data=b"", sample_rate=16000)
        self.state = VoiceState.PROCESSING
        text = await self.stt.transcribe(chunk)
        self.state = VoiceState.IDLE
        return text

    async def speak(self, text: str) -> None:
        """Synthesize and play back text as speech.

        Args:
            text: The text to speak aloud.
        """
        self.state = VoiceState.SPEAKING
        logger.debug("VoiceModule: speaking '%s'", text[:80])
        audio = await self.tts.synthesize(text)
        # In production, play audio chunk here
        self.state = VoiceState.IDLE

    async def cleanup(self) -> None:
        """Release all voice subsystem resources."""
        await self.stt.cleanup()
        await self.tts.cleanup()
        logger.info("VoiceModule cleaned up")
