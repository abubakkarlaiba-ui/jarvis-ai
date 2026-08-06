"""
Text-to-Speech engine for JARVIS with multiple voice personalities.
==================================================================
Provides natural-sounding speech synthesis with configurable voices,
speaking speed, pitch, and volume.

Supports multiple backends:
    - edge-tts: Free, high-quality Microsoft Edge voices (default)
    - elevenlabs: Premium AI voices (requires API key)
    - pyttsx3: Offline fallback using system TTS

Voice personalities are pre-configured profiles that map to specific
TTS voices and speaking styles.

Usage:
    tts = TTSEngine(settings)
    await tts.initialize()
    audio = await tts.speak("Hello, sir.")
    await tts.speak("Goodbye.", personality="friday")
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
import wave
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Optional

import numpy as np

from jarvis.config.settings import VoiceSettings

logger = logging.getLogger(__name__)


class VoicePersonality(Enum):
    """Pre-configured voice profiles for different JARVIS personas."""
    JARVIS = "jarvis"
    FRIDAY = "friday"
    FRIDAY_KID = "friday_kid"
    BRITISH_BUTLER = "british_butler"
    CUSTOM = "custom"


@dataclass
class VoiceProfile:
    """Configuration for a voice personality."""
    name: str
    voice_id: str  # Backend-specific voice identifier
    rate: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0
    description: str = ""


# Pre-configured voice personalities
VOICE_PROFILES: dict[str, VoiceProfile] = {
    VoicePersonality.JARVIS.value: VoiceProfile(
        name="JARVIS",
        voice_id="en-US-GuyNeural",
        rate=1.05,
        pitch=0.0,
        volume=1.0,
        description="Calm, authoritative male voice — the classic JARVIS",
    ),
    VoicePersonality.FRIDAY.value: VoiceProfile(
        name="FRIDAY",
        voice_id="en-US-AriaNeural",
        rate=1.0,
        pitch=2.0,
        volume=0.95,
        description="Clear, professional female voice",
    ),
    VoicePersonality.FRIDAY_KID.value: VoiceProfile(
        name="FRIDAY Kid",
        voice_id="en-US-JennyNeural",
        rate=1.1,
        pitch=5.0,
        volume=1.0,
        description="Energetic, youthful female voice",
    ),
    VoicePersonality.BRITISH_BUTLER.value: VoiceProfile(
        name="British Butler",
        voice_id="en-GB-RyanNeural",
        rate=0.95,
        pitch=-1.0,
        volume=0.9,
        description="Refined British male voice",
    ),
}


class EdgeTTSBackend:
    """Microsoft Edge TTS backend — free, high-quality neural voices.

    Uses the edge-tts package to access Microsoft's neural TTS voices
    without an API key.
    """

    def __init__(self):
        self._communicate = None

    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: float = 1.0,
        volume: float = 1.0,
        pitch: float = 0.0,
    ) -> AsyncIterator[bytes]:
        """Synthesize text and yield audio chunks.

        Args:
            text: Text to synthesize.
            voice: Voice identifier (e.g., "en-US-GuyNeural").
            rate: Speaking rate multiplier (0.5-3.0).
            volume: Volume multiplier (0.0-2.0).
            pitch: Pitch adjustment in Hz.

        Yields:
            PCM audio bytes chunks.
        """
        try:
            import edge_tts

            # Format rate as "+0%" or "-10%"
            rate_str = f"+{int((rate - 1.0) * 100)}%" if rate >= 1.0 else f"{int((rate - 1.0) * 100)}%"
            vol_str = f"+{int((volume - 1.0) * 100)}%" if volume >= 1.0 else f"{int((volume - 1.0) * 100)}%"
            pitch_str = f"+{int(pitch)}Hz" if pitch >= 0 else f"{int(pitch)}Hz"

            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=rate_str,
                volume=vol_str,
                pitch=pitch_str,
            )

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
            raise
        except Exception as exc:
            logger.error("Edge TTS synthesis failed: %s", exc)
            raise

    async def list_voices(self, language: str = "en") -> list[dict]:
        """List available Edge TTS voices.

        Args:
            language: Language filter (e.g., "en", "es").

        Returns:
            List of voice info dictionaries.
        """
        try:
            import edge_tts
            voices = await edge_tts.list_voices()
            if language:
                voices = [v for v in voices if v.get("Locale", "").startswith(language)]
            return voices
        except Exception as exc:
            logger.error("Failed to list Edge TTS voices: %s", exc)
            return []


class ElevenLabsBackend:
    """ElevenLabs premium TTS backend.

    Uses the ElevenLabs API for ultra-realistic AI voices.
    Requires an API key set in ELEVENLABS_API_KEY or VOICE_TTS_API_KEY.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        self._client = None

    async def initialize(self) -> None:
        """Initialize the ElevenLabs client."""
        if not self._api_key:
            logger.warning("ElevenLabs API key not set, TTS will not work")
            return

        try:
            import elevenlabs
            elevenlabs.set_api_key(self._api_key)
            self._client = elevenlabs
            logger.info("ElevenLabs TTS initialized")
        except ImportError:
            logger.error("elevenlabs not installed. Run: pip install elevenlabs")
        except Exception as exc:
            logger.error("Failed to initialize ElevenLabs: %s", exc)

    async def synthesize(
        self,
        text: str,
        voice_id: str = "Rachel",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
    ) -> AsyncIterator[bytes]:
        """Synthesize text using ElevenLabs API.

        Args:
            text: Text to synthesize.
            voice_id: Voice name or ID.
            stability: Voice stability (0.0-1.0).
            similarity_boost: Similarity boost (0.0-1.0).

        Yields:
            Audio data chunks.
        """
        if not self._client:
            raise RuntimeError("ElevenLabs not initialized")

        try:
            audio = self._client.generate(
                text=text,
                voice=voice_id,
                model="eleven_monolingual_v1",
            )
            # ElevenLabs returns a generator of bytes
            for chunk in audio:
                yield chunk

        except Exception as exc:
            logger.error("ElevenLabs synthesis failed: %s", exc)
            raise


class Pyttsx3Backend:
    """Offline pyttsx3 TTS fallback.

    Uses system-installed TTS engines (SAPI5 on Windows, espeak on Linux).
    Lower quality but works without internet or API keys.
    """

    def __init__(self):
        self._engine = None

    def _init_engine(self):
        """Initialize pyttsx3 engine (must be called from sync context)."""
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            logger.info("pyttsx3 TTS engine initialized")
        except Exception as exc:
            logger.error("Failed to initialize pyttsx3: %s", exc)

    async def synthesize_to_file(self, text: str, output_path: str, rate: int = 200, voice_id: str | None = None) -> bool:
        """Synthesize text to a WAV file.

        Args:
            text: Text to speak.
            output_path: Path for the output WAV file.
            rate: Words per minute.
            voice_id: System voice identifier.

        Returns:
            True on success.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._synthesize_file, text, output_path, rate, voice_id)

    def _synthesize_file(self, text: str, output_path: str, rate: int, voice_id: str | None) -> bool:
        if self._engine is None:
            self._init_engine()
        if self._engine is None:
            return False

        try:
            self._engine.setProperty("rate", rate)
            if voice_id:
                self._engine.setProperty("voice", voice_id)
            self._engine.save_to_file(text, output_path)
            self._engine.runAndWait()
            return os.path.exists(output_path)
        except Exception as exc:
            logger.error("pyttsx3 synthesis failed: %s", exc)
            return False


class TTSEngine:
    """Unified TTS engine with voice personalities and interrupt support.

    Coordinates between backends and manages playback state for
    interrupt-when-user-speaks behavior.

    Features:
        - Multiple voice personalities (JARVIS, FRIDAY, etc.)
        - Adjustable speed, pitch, volume per personality
        - Interrupt support (stop speaking when user starts)
        - Streaming audio output
        - Fallback chain: edge-tts → elevenlabs → pyttsx3

    Example:
        tts = TTSEngine(settings)
        await tts.initialize()
        await tts.speak("Hello, sir.")
        await tts.speak("Goodbye.", personality="friday")
    """

    def __init__(self, settings: VoiceSettings):
        self._settings = settings
        self._personality = settings.tts_personality
        self._rate = settings.tts_rate
        self._volume = settings.tts_volume
        self._pitch = settings.tts_pitch

        # Backends (initialized lazily)
        self._edge = EdgeTTSBackend()
        self._elevenlabs: ElevenLabsBackend | None = None
        self._pyttsx3: Pyttsx3Backend | None = None

        self._active_backend: str = "edge_tts"
        self._is_speaking = False
        self._should_interrupt = False
        self._speak_lock = asyncio.Lock()
        self._initialized = False
        self._utterance_count = 0

        logger.info("TTSEngine created (personality=%s, rate=%.2f)", self._personality, self._rate)

    async def initialize(self) -> None:
        """Initialize the primary TTS backend."""
        if self._initialized:
            return

        engine = self._settings.tts_engine

        if engine == "elevenlabs":
            self._elevenlabs = ElevenLabsBackend()
            await self._elevenlabs.initialize()
            self._active_backend = "elevenlabs"
        elif engine == "pyttsx3":
            self._pyttsx3 = Pyttsx3Backend()
            self._active_backend = "pyttsx3"
        else:
            # edge_tts is default
            self._active_backend = "edge_tts"

        self._initialized = True
        logger.info("TTSEngine initialized (backend=%s)", self._active_backend)

    async def speak(
        self,
        text: str,
        personality: str | None = None,
        interruptible: bool = True,
    ) -> bool:
        """Synthesize and yield audio for the given text.

        This method handles the full pipeline: text → synthesize → yield bytes.
        The caller is responsible for playback.

        Args:
            text: Text to speak.
            personality: Voice personality override (uses default if None).
            interruptible: Whether this utterance can be interrupted.

        Returns:
            True if synthesis completed, False if interrupted.
        """
        if not self._initialized:
            await self.initialize()

        if not text or not text.strip():
            return False

        # Resolve voice profile
        profile = self._get_profile(personality or self._personality)

        # Apply rate/volume overrides from profile
        rate = profile.rate * self._rate
        volume = profile.volume * self._volume
        pitch = profile.pitch + self._pitch

        async with self._speak_lock:
            self._is_speaking = True
            self._should_interrupt = False

        try:
            logger.debug("TTS speaking: '%s' [voice=%s, rate=%.2f]", text[:60], profile.voice_id, rate)

            if self._active_backend == "edge_tts":
                async for chunk in self._edge.synthesize(
                    text, profile.voice_id, rate=rate, volume=volume, pitch=pitch
                ):
                    if interruptible and self._should_interrupt:
                        logger.debug("TTS interrupted by user")
                        return False
                    yield chunk

            elif self._active_backend == "elevenlabs" and self._elevenlabs:
                async for chunk in self._elevenlabs.synthesize(text, profile.voice_id):
                    if interruptible and self._should_interrupt:
                        return False
                    yield chunk

            elif self._active_backend == "pyttsx3" and self._pyttsx3:
                # For pyttsx3, synthesize to a temp file then yield bytes
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp_path = f.name
                rate_wpm = int(200 * rate)
                success = await self._pyttsx3.synthesize_to_file(
                    text, tmp_path, rate=rate_wpm, voice_id=profile.voice_id
                )
                if success:
                    audio_bytes = Path(tmp_path).read_bytes()
                    if interruptible and self._should_interrupt:
                        os.unlink(tmp_path)
                        return False
                    yield audio_bytes
                os.unlink(tmp_path) if os.path.exists(tmp_path) else None

            self._utterance_count += 1
            return True

        except Exception as exc:
            logger.error("TTS speak failed: %s", exc)
            return False

        finally:
            async with self._speak_lock:
                self._is_speaking = False

    async def speak_sync(self, text: str, personality: str | None = None) -> bool:
        """Synthesize text and collect all audio bytes (non-streaming).

        Args:
            text: Text to speak.
            personality: Voice personality override.

        Returns:
            True on success.
        """
        chunks = []
        async for chunk in self.speak(text, personality, interruptible=False):
            chunks.append(chunk)
        return len(chunks) > 0

    def interrupt(self) -> None:
        """Signal the engine to stop the current utterance."""
        self._should_interrupt = True
        logger.debug("TTS interrupt requested")

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def is_interrupted(self) -> bool:
        return self._should_interrupt

    def set_personality(self, personality: str) -> None:
        """Change the active voice personality.

        Args:
            personality: Personality name (jarvis, friday, etc.)

        Raises:
            ValueError: If the personality is not registered.
        """
        if personality not in VOICE_PROFILES and personality != VoicePersonality.CUSTOM.value:
            raise ValueError(f"Unknown personality: {personality}. Available: {list(VOICE_PROFILES.keys())}")
        self._personality = personality
        logger.info("TTS personality changed to: %s", personality)

    def set_rate(self, rate: float) -> None:
        """Adjust the speaking rate multiplier."""
        self._rate = max(0.5, min(3.0, rate))
        logger.info("TTS rate set to: %.2f", self._rate)

    def set_volume(self, volume: float) -> None:
        """Adjust the volume multiplier."""
        self._volume = max(0.0, min(2.0, volume))

    def set_pitch(self, pitch: float) -> None:
        """Adjust the pitch in Hz."""
        self._pitch = pitch

    def _get_profile(self, name: str) -> VoiceProfile:
        """Resolve a voice profile by name."""
        if name in VOICE_PROFILES:
            return VOICE_PROFILES[name]
        # Fallback to JARVIS profile
        logger.warning("Unknown voice profile '%s', using JARVIS", name)
        return VOICE_PROFILES[VoicePersonality.JARVIS.value]

    def list_personalities(self) -> list[dict]:
        """Return all available voice personalities."""
        return [
            {
                "name": p.name,
                "key": key,
                "voice_id": p.voice_id,
                "rate": p.rate,
                "description": p.description,
            }
            for key, p in VOICE_PROFILES.items()
        ]

    async def list_voices(self) -> list[dict]:
        """List all available voices from the active backend."""
        if self._active_backend == "edge_tts":
            return await self._edge.list_voices()
        return []

    async def cleanup(self) -> None:
        """Release TTS resources."""
        self._is_speaking = False
        self._should_interrupt = False
        logger.info("TTSEngine cleaned up")

    @property
    def stats(self) -> dict:
        return {
            "backend": self._active_backend,
            "personality": self._personality,
            "rate": self._rate,
            "volume": self._volume,
            "pitch": self._pitch,
            "is_speaking": self._is_speaking,
            "utterances": self._utterance_count,
        }
