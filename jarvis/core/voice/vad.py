"""
Voice Activity Detection (VAD) for JARVIS.
==========================================
Detects when the user is speaking versus silence.

Uses Silero VAD for accurate, low-latency voice activity detection.
Silero runs a small neural network on short audio windows and outputs
a probability score (0.0–1.0) of speech being present.

The VAD operates in two modes:
    - Window mode: analyze a fixed-size chunk, return speech probability
    - Stream mode: track state across chunks, fire events on speech start/end

Usage:
    vad = VoiceActivityDetector(settings)
    is_speech = vad.is_speech(audio_float32)
    event = vad.update(audio_float32)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import numpy as np

from jarvis.config.settings import VoiceSettings

logger = logging.getLogger(__name__)


class VADEvent(Enum):
    """Events emitted by the VAD state machine."""
    NONE = auto()
    SPEECH_START = auto()
    SPEECH_CONTINUE = auto()
    SPEECH_END = auto()
    SILENCE = auto()


@dataclass
class VADState:
    """Internal state of the VAD tracker."""
    is_speech: bool = False
    speech_start_time: float = 0.0
    last_speech_time: float = 0.0
    speech_probability: float = 0.0
    consecutive_speech_frames: int = 0
    consecutive_silence_frames: int = 0


class SileroVAD:
    """Wrapper around the Silero VAD ONNX model.

    Loads the pre-trained model and runs inference on audio windows.
    Falls back to energy-based detection if the model is unavailable.
    """

    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self._model = None
        self._session = None
        self._h: Optional[np.ndarray] = None
        self._c: Optional[np.ndarray] = None
        self._initialized = False

    def initialize(self) -> None:
        """Load the Silero VAD model."""
        try:
            import onnxruntime as ort
            import os
            # Try to find the bundled model
            model_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "data", "models", "silero_vad.onnx"
            )
            if os.path.exists(model_path):
                self._session = ort.InferenceSession(model_path)
                self._h = np.zeros((2, 1, 64), dtype=np.float32)
                self._c = np.zeros((2, 1, 64), dtype=np.float32)
                self._initialized = True
                logger.info("Silero VAD model loaded from %s", model_path)
            else:
                logger.warning("Silero VAD model not found at %s, using energy fallback", model_path)
        except ImportError:
            logger.warning("onnxruntime not installed, using energy-based VAD fallback")
        except Exception as exc:
            logger.error("Failed to load Silero VAD: %s", exc)

    def predict(self, audio: np.ndarray) -> float:
        """Run VAD inference on an audio window.

        Args:
            audio: Float32 audio samples (typically 512 samples for 16kHz).

        Returns:
            Speech probability between 0.0 and 1.0.
        """
        if self._initialized and self._session is not None:
            return self._predict_silero(audio)
        return self._predict_energy(audio)

    def _predict_silero(self, audio: np.ndarray) -> float:
        """Run Silero model inference."""
        # Ensure correct shape and type
        audio_input = audio.astype(np.float32)
        if len(audio_input) != 512:
            # Pad or truncate to 512 samples (32ms at 16kHz)
            if len(audio_input) < 512:
                audio_input = np.pad(audio_input, (0, 512 - len(audio_input)))
            else:
                audio_input = audio_input[:512]

        audio_input = audio_input.reshape(1, -1)

        input_name = self._session.get_inputs()[0].name
        sr_input = self._session.get_inputs()[1].name if len(self._session.get_inputs()) > 1 else None

        if sr_input:
            prob, self._h, self._c = self._session.run(
                None,
                {
                    input_name: audio_input,
                    sr_input: np.array([self.sample_rate], dtype=np.int64),
                    "h": self._h,
                    "c": self._c,
                },
            )
        else:
            prob, self._h, self._c = self._session.run(
                None,
                {input_name: audio_input, "h": self._h, "c": self._c},
            )

        return float(prob[0][0])

    def _predict_energy(self, audio: np.ndarray) -> float:
        """Energy-based VAD fallback when Silero is unavailable."""
        if len(audio) == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(audio ** 2)))
        # Map RMS energy to probability with soft sigmoid
        # Threshold around 0.02-0.05 RMS for typical speech
        normalized = rms / 0.1  # normalize by expected speech level
        probability = min(1.0, normalized * 2.0)
        return probability

    def reset(self) -> None:
        """Reset internal state for a new session."""
        if self._h is not None:
            self._h = np.zeros_like(self._h)
        if self._c is not None:
            self._c = np.zeros_like(self._c)


class VoiceActivityDetector:
    """High-level VAD with state machine tracking.

    Wraps SileroVAD with speech start/end event detection,
    configurable thresholds, and timing.

    Usage:
        vad = VoiceActivityDetector(settings)
        for audio_chunk in stream:
            event = vad.update(audio_chunk)
            if event == VADEvent.SPEECH_START:
                print("User started talking!")
            elif event == VADEvent.SPEECH_END:
                print("User finished talking.")
    """

    def __init__(self, settings: VoiceSettings):
        self.threshold = settings.vad_threshold
        self.speech_duration_ms = settings.vad_speech_duration_ms
        self.silence_duration_ms = settings.vad_silence_duration_ms
        self.speech_pad_ms = settings.vad_speech_pad_ms

        self._silero = SileroVAD(
            threshold=settings.vad_threshold,
            sample_rate=settings.mic_sample_rate,
        )
        self._state = VADState()
        self._window_size = 512  # samples per inference window

        # Derived frame counts
        frames_per_ms = settings.mic_sample_rate / self._window_size
        self._min_speech_frames = max(1, int(self.speech_duration_ms * frames_per_ms / 1000))
        self._min_silence_frames = max(1, int(self.silence_duration_ms * frames_per_ms / 1000))
        self._pad_frames = max(0, int(self.speech_pad_ms * frames_per_ms / 1000))

        logger.info(
            "VoiceActivityDetector initialized (threshold=%.2f, speech_ms=%d, silence_ms=%d)",
            self.threshold,
            self.speech_duration_ms,
            self.silence_duration_ms,
        )

    def initialize(self) -> None:
        """Load the underlying VAD model."""
        self._silero.initialize()

    def is_speech(self, audio: np.ndarray) -> bool:
        """Quick check: does this audio chunk contain speech?

        Args:
            audio: Float32 audio samples.

        Returns:
            True if speech probability exceeds threshold.
        """
        prob = self._silero.predict(audio)
        return prob >= self.threshold

    def get_probability(self, audio: np.ndarray) -> float:
        """Return the raw speech probability for an audio chunk."""
        return self._silero.predict(audio)

    def update(self, audio: np.ndarray) -> VADEvent:
        """Process an audio chunk and return the VAD event.

        The state machine tracks transitions between speech and silence,
        applying duration requirements before firing events.

        Args:
            audio: Float32 audio samples (one window, typically 512 samples).

        Returns:
            VADEvent indicating the current state transition.
        """
        prob = self._silero.predict(audio)
        self._state.speech_probability = prob

        now = time.monotonic()

        if prob >= self.threshold:
            # Speech detected
            self._state.consecutive_speech_frames += 1
            self._state.consecutive_silence_frames = 0
            self._state.last_speech_time = now

            if not self._state.is_speech:
                # Potential speech start — check duration requirement
                if self._state.consecutive_speech_frames >= self._min_speech_frames:
                    self._state.is_speech = True
                    self._state.speech_start_time = now - (
                        self._state.consecutive_speech_frames * self._window_size / 16000
                    )
                    logger.debug("VAD: SPEECH_START (prob=%.3f)", prob)
                    return VADEvent.SPEECH_START
                return VADEvent.NONE
            else:
                return VADEvent.SPEECH_CONTINUE
        else:
            # Silence detected
            self._state.consecutive_silence_frames += 1
            self._state.consecutive_speech_frames = 0

            if self._state.is_speech:
                # Check if silence long enough to end speech
                if self._state.consecutive_silence_frames >= self._min_silence_frames:
                    self._state.is_speech = False
                    duration = now - self._state.speech_start_time
                    logger.debug("VAD: SPEECH_END (duration=%.2fs)", duration)
                    return VADEvent.SPEECH_END
                return VADEvent.SPEECH_CONTINUE
            else:
                return VADEvent.SILENCE

    def reset(self) -> None:
        """Reset state for a new listening session."""
        self._state = VADState()
        self._silero.reset()

    @property
    def state(self) -> VADState:
        return self._state

    @property
    def is_currently_speaking(self) -> bool:
        return self._state.is_speech
