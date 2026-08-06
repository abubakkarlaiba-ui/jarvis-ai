"""
Whisper-based Speech-to-Text engine for JARVIS.
================================================
Uses OpenAI's Whisper model for accurate, multilingual speech recognition.

Supports both the faster-whisper (CTranslate2) backend for local inference
and the OpenAI API for cloud-based transcription.

Latency profile (base model, CPU):
    - Model load: ~2s (one-time)
    - Transcription: ~0.3-0.8s for short utterances (<5s audio)

Usage:
    stt = WhisperSTT(settings)
    await stt.initialize()
    text = await stt.transcribe(audio_float32_array)
"""

from __future__ import annotations

import asyncio
import io
import logging
import struct
import time
from typing import Optional

import numpy as np

from jarvis.config.settings import VoiceSettings

logger = logging.getLogger(__name__)


class WhisperSTT:
    """Whisper-based speech-to-text engine.

    Automatically selects the best available backend:
        1. faster-whisper (local, fastest)
        2. openai-whisper (local, reference implementation)
        3. OpenAI API (cloud, requires API key)

    Example:
        stt = WhisperSTT(settings)
        await stt.initialize()
        text = await stt.transcribe(audio_float32)
    """

    def __init__(self, settings: VoiceSettings):
        self._model_name = settings.whisper_model
        self._language = settings.whisper_language
        self._device = settings.whisper_device
        self._beam_size = settings.whisper_beam_size
        self._fp16 = settings.whisper_fp16
        self._api_key = settings.tts_voice_id  # reuse from settings or AI settings

        self._model = None
        self._backend: str = "none"
        self._initialized = False
        self._transcription_count = 0

    async def initialize(self) -> None:
        """Load the Whisper model in a thread to avoid blocking."""
        if self._initialized:
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model)
        self._initialized = True
        logger.info("WhisperSTT initialized (backend=%s, model=%s, device=%s)",
                     self._backend, self._model_name, self._device)

    def _load_model(self) -> None:
        """Load the Whisper model (runs in executor)."""
        # Try faster-whisper first (best performance)
        try:
            from faster_whisper import WhisperModel
            compute_type = "float16" if self._fp16 and self._device == "cuda" else "int8"
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=compute_type,
            )
            self._backend = "faster-whisper"
            logger.info("Loaded faster-whisper model: %s", self._model_name)
            return
        except ImportError:
            logger.debug("faster-whisper not available, trying openai-whisper")
        except Exception as exc:
            logger.warning("faster-whisper failed to load: %s", exc)

        # Try openai-whisper (reference implementation)
        try:
            import whisper
            self._model = whisper.load_model(
                self._model_name,
                device=self._device,
            )
            self._backend = "openai-whisper"
            logger.info("Loaded openai-whisper model: %s", self._model_name)
            return
        except ImportError:
            logger.debug("openai-whisper not available")
        except Exception as exc:
            logger.warning("openai-whisper failed to load: %s", exc)

        # Fallback: use OpenAI API if key is available
        logger.warning("No local Whisper backend available. Set AI_API_KEY for cloud transcription.")
        self._backend = "none"

    async def transcribe(self, audio: np.ndarray | bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio to text.

        Args:
            audio: Float32 numpy array or raw PCM bytes.
            sample_rate: Sample rate of the audio (default 16000).

        Returns:
            Transcribed text, or empty string if transcription fails.
        """
        if not self._initialized:
            await self.initialize()

        if self._backend == "none":
            logger.error("No STT backend available")
            return ""

        # Convert bytes to float32 if needed
        if isinstance(audio, bytes):
            audio = self._bytes_to_float32(audio)

        if audio is None or len(audio) == 0:
            return ""

        # Minimum audio length check (<0.3s is likely noise)
        duration = len(audio) / sample_rate
        if duration < 0.3:
            return ""

        start = time.perf_counter()
        loop = asyncio.get_event_loop()

        try:
            text = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                audio,
                sample_rate,
            )
            elapsed = time.perf_counter() - start
            self._transcription_count += 1

            if text.strip():
                logger.info(
                    "STT [%s] %.2fs audio → %.3fs processing: '%s'",
                    self._backend,
                    duration,
                    elapsed,
                    text[:80],
                )
            else:
                logger.debug("STT: no speech detected in %.2fs audio", duration)

            return text.strip()

        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error("STT failed after %.3fs: %s", elapsed, exc)
            return ""

    def _transcribe_sync(self, audio: np.ndarray, sample_rate: int) -> str:
        """Synchronous transcription (runs in thread executor)."""
        if self._backend == "faster-whisper":
            return self._transcribe_faster_whisper(audio, sample_rate)
        elif self._backend == "openai-whisper":
            return self._transcribe_openai_whisper(audio, sample_rate)
        return ""

    def _transcribe_faster_whisper(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe using faster-whisper CTranslate2 backend."""
        # faster-whisper expects float32 numpy array
        audio_f32 = audio.astype(np.float32)

        segments, info = self._model.transcribe(
            audio_f32,
            language=self._language if self._language != "auto" else None,
            beam_size=self._beam_size,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        text_parts = [segment.text for segment in segments]
        return " ".join(text_parts).strip()

    def _transcribe_openai_whisper(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe using openai-whisper reference implementation."""
        audio_f32 = audio.astype(np.float32)

        # whisper expects 16kHz float32
        result = self._model.transcribe(
            audio_f32,
            language=self._language if self._language != "auto" else None,
            beam_size=self._beam_size,
            fp16=self._fp16,
        )

        return result.get("text", "").strip()

    async def transcribe_streaming(
        self,
        audio_chunks: list[np.ndarray],
        sample_rate: int = 16000,
    ) -> str:
        """Transcribe multiple audio chunks as a single utterance.

        Useful for streaming VAD-detected speech segments.

        Args:
            audio_chunks: List of float32 audio arrays to concatenate.
            sample_rate: Sample rate of the audio.

        Returns:
            Combined transcription text.
        """
        if not audio_chunks:
            return ""

        combined = np.concatenate(audio_chunks)
        return await self.transcribe(combined, sample_rate)

    @staticmethod
    def _bytes_to_float32(data: bytes) -> Optional[np.ndarray]:
        """Convert raw PCM bytes to float32 numpy array."""
        if not data or len(data) < 2:
            return None

        num_samples = len(data) // 2
        int16_data = np.frombuffer(data[:num_samples * 2], dtype=np.int16)
        return int16_data.astype(np.float32) / 32768.0

    async def cleanup(self) -> None:
        """Release model resources."""
        self._model = None
        self._initialized = False
        logger.info("WhisperSTT cleaned up")

    @property
    def stats(self) -> dict:
        return {
            "backend": self._backend,
            "model": self._model_name,
            "device": self._device,
            "initialized": self._initialized,
            "transcriptions": self._transcription_count,
        }
