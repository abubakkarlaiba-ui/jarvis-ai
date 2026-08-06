"""
Audio processing pipeline for JARVIS voice input.
=================================================
Provides noise reduction, gain normalization, and audio formatting
to clean raw microphone input before STT processing.

The pipeline runs a chain of lightweight DSP operations optimized
for real-time voice interaction:

    Raw Audio → Gate → Normalize → Reduce Noise → Float32 Array

Usage:
    from jarvis.core.voice.audio_processor import AudioProcessor
    processor = AudioProcessor(settings)
    clean = processor.process(raw_pcm_bytes)
"""

from __future__ import annotations

import logging
import math
import struct
from dataclasses import dataclass
from typing import Optional

import numpy as np

from jarvis.config.settings import VoiceSettings

logger = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    """Audio format descriptor."""
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # bytes per sample (16-bit)


class NoiseGate:
    """Simple noise gate that zeros out frames below an energy threshold.

    Prevents low-level background noise from being passed downstream.
    """

    def __init__(self, threshold: float = 0.01, attack_ms: float = 5, release_ms: float = 50):
        self.threshold = threshold
        self.attack_frames = int(attack_ms * 0.001 * 16000)
        self.release_frames = int(release_ms * 0.001 * 16000)
        self._gain = 0.0

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply noise gate to audio signal.

        Args:
            audio: Float32 normalized audio array.

        Returns:
            Gated audio with noise suppressed below threshold.
        """
        if len(audio) == 0:
            return audio

        envelope = np.abs(audio)
        rms = float(np.sqrt(np.mean(envelope ** 2)))

        if rms > self.threshold:
            self._gain = min(1.0, self._gain + 1.0 / max(self.attack_frames, 1))
        else:
            self._gain = max(0.0, self._gain - 1.0 / max(self.release_frames, 1))

        return audio * self._gain


class SpectralNoiseReducer:
    """Frequency-domain noise reduction using spectral gating.

    Estimates the noise profile from quiet frames and subtracts it
    from active speech frames via FFT masking.
    """

    def __init__(self, strength: float = 0.5, sample_rate: int = 16000):
        self.strength = strength
        self.sample_rate = sample_rate
        self.noise_profile: Optional[np.ndarray] = None
        self._calibration_frames: list[np.ndarray] = []
        self._calibration_needed = 10

    def calibrate(self, audio: np.ndarray) -> None:
        """Feed calibration audio to estimate noise profile.

        Call this during silence periods before speech begins.

        Args:
            audio: Float32 audio chunk during silence.
        """
        self._calibration_frames.append(audio)
        if len(self._calibration_frames) >= self._calibration_needed:
            combined = np.concatenate(self._calibration_frames)
            fft = np.fft.rfft(combined)
            self.noise_profile = np.abs(fft) * 1.2  # 20% margin
            self._calibration_frames.clear()
            logger.debug("Noise profile calibrated from %d frames", self._calibration_needed)

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply spectral noise reduction to audio.

        Args:
            audio: Float32 audio chunk.

        Returns:
            Denoised audio array.
        """
        if self.noise_profile is None or self.strength <= 0:
            return audio

        n = len(audio)
        fft = np.fft.rfft(audio)
        magnitude = np.abs(fft)
        phase = np.angle(fft)

        # Spectral subtraction with flooring
        clean_magnitude = magnitude - (self.noise_profile[:n // 2 + 1] * self.strength)
        clean_magnitude = np.maximum(clean_magnitude, 0.0)

        # Reconstruct
        clean_fft = clean_magnitude * np.exp(1j * phase)
        clean_audio = np.fft.irfft(clean_fft, n=n)

        return clean_audio.astype(np.float32)


class AudioProcessor:
    """Full audio processing pipeline.

    Chains together noise gate, spectral reduction, and gain normalization
    to produce clean audio for STT processing.

    Pipeline:
        Raw PCM bytes → int16 → float32 → Gate → Noise Reduce → Normalize

    Example:
        processor = AudioProcessor(settings)
        clean_float = processor.process(raw_pcm_bytes)
        # clean_float is float32 numpy array at 16kHz mono
    """

    def __init__(self, settings: VoiceSettings):
        self.config = AudioConfig(
            sample_rate=settings.mic_sample_rate,
            channels=settings.mic_channels,
        )
        self.noise_gate = NoiseGate(
            threshold=settings.noise_gate_threshold,
        )
        self.noise_reducer = SpectralNoiseReducer(
            strength=settings.noise_reduction_strength if settings.noise_reduction_enabled else 0.0,
            sample_rate=settings.mic_sample_rate,
        )
        self._calibration_mode = False
        self._frame_count = 0
        logger.info(
            "AudioProcessor initialized (gate=%.3f, noise_reduce=%.2f)",
            settings.noise_gate_threshold,
            settings.noise_reduction_strength,
        )

    def process(self, raw_pcm: bytes) -> np.ndarray:
        """Process raw PCM bytes through the full pipeline.

        Args:
            raw_pcm: Raw 16-bit signed PCM audio bytes.

        Returns:
            Clean float32 numpy array normalized to [-1.0, 1.0].
        """
        if not raw_pcm or len(raw_pcm) < 2:
            return np.array([], dtype=np.float32)

        # Convert bytes to int16 array
        num_samples = len(raw_pcm) // 2
        int16_data = np.frombuffer(raw_pcm[:num_samples * 2], dtype=np.int16)

        # Normalize to float32 [-1.0, 1.0]
        float_data = int16_data.astype(np.float32) / 32768.0

        # Ensure mono (average channels if stereo)
        if self.config.channels == 2 and len(float_data) > 1:
            float_data = float_data.reshape(-1, 2).mean(axis=1)

        # Calibration mode: collect quiet frames for noise profiling
        if self._calibration_mode:
            self.noise_reducer.calibrate(float_data)
            return float_data

        # Apply noise gate
        gated = self.noise_gate.process(float_data)

        # Apply spectral noise reduction
        cleaned = self.noise_reducer.process(gated)

        # Peak normalization (soft limiter to avoid clipping)
        peak = float(np.max(np.abs(cleaned))) if len(cleaned) > 0 else 0.0
        if peak > 0.95:
            cleaned = cleaned * (0.95 / peak)
        elif peak > 0.0 and peak < 0.1:
            # Boost very quiet audio
            cleaned = cleaned * min(2.0, 0.3 / peak)

        self._frame_count += 1
        return cleaned

    def process_to_pcm(self, raw_pcm: bytes) -> bytes:
        """Process audio and return as PCM bytes (for passing to models)."""
        float_data = self.process(raw_pcm)
        if len(float_data) == 0:
            return b""
        int16_data = (float_data * 32767).clip(-32768, 32767).astype(np.int16)
        return int16_data.tobytes()

    def start_calibration(self) -> None:
        """Enter calibration mode to learn noise profile."""
        self._calibration_mode = True
        self.noise_reducer._calibration_frames.clear()
        self.noise_reducer.noise_profile = None
        logger.info("Audio calibration started — speak nothing for a moment")

    def stop_calibration(self) -> bool:
        """Exit calibration mode.

        Returns:
            True if a noise profile was successfully learned.
        """
        self._calibration_mode = False
        has_profile = self.noise_reducer.noise_profile is not None
        logger.info("Audio calibration stopped (profile=%s)", "ok" if has_profile else "missing")
        return has_profile

    @property
    def is_calibrating(self) -> bool:
        return self._calibration_mode

    @property
    def stats(self) -> dict:
        return {
            "frames_processed": self._frame_count,
            "calibrating": self._calibration_mode,
            "noise_profile_ready": self.noise_reducer.noise_profile is not None,
        }
