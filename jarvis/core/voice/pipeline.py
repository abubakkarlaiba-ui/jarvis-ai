"""
Voice pipeline — the complete voice interaction orchestrator for JARVIS.
======================================================================
Wires together microphone, VAD, wake word, STT, TTS, audio processing,
and conversation logging into a seamless, low-latency voice loop.

Interaction flow:
    ┌─────────┐    ┌─────┐    ┌───────────┐    ┌─────┐    ┌─────┐
    │  Mic    │───▶│ ADP │───▶│ Wake Word │───▶│ STT │───▶│Brain│
    └─────────┘    └─────┘    └───────────┘    └─────┘    └─────┘
                      │                            ▲          │
                      │         ┌─────┐            │          ▼
                      └────────▶│ VAD │────────────┘      ┌─────┐
                                └─────┘                    │ TTS │───▶ Speaker
                                                           └─────┘

Key behaviors:
    - Always-on wake word detection (low CPU via VAD gating)
    - Automatic interrupt: user speech stops JARVIS mid-sentence
    - Continuous listening mode for multi-turn conversations
    - Every audio frame is processed through noise reduction
    - All turns are logged for review

Usage:
    pipeline = VoicePipeline(settings)
    await pipeline.initialize()
    # Start the interaction loop
    await pipeline.run(command_handler=my_handler)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Awaitable, Callable, Optional

import numpy as np

from jarvis.config.settings import VoiceSettings
from jarvis.core.voice.audio_processor import AudioProcessor
from jarvis.core.voice.vad import VoiceActivityDetector, VADEvent
from jarvis.core.voice.microphone import MicrophoneManager, AudioFrame
from jarvis.core.voice.whisper_stt import WhisperSTT
from jarvis.core.voice.tts_engine import TTSEngine
from jarvis.core.voice.wake_word import WakeWordDetector
from jarvis.core.voice.voice_logger import VoiceLogger

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """States of the voice pipeline state machine."""
    BOOTING = auto()
    IDLE = auto()
    LISTENING_FOR_WAKE = auto()
    LISTENING_FOR_COMMAND = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    INTERRUPTED = auto()
    SHUTDOWN = auto()


# Type for the command handler callback
CommandHandler = Callable[[str], Awaitable[str]]


@dataclass
class PipelineMetrics:
    """Performance metrics for the voice pipeline."""
    frames_processed: int = 0
    wake_word_detections: int = 0
    commands_processed: int = 0
    total_speech_ms: float = 0.0
    total_processing_ms: float = 0.0
    total_tts_ms: float = 0.0
    interrupts: int = 0
    average_stt_latency_ms: float = 0.0
    average_roundtrip_ms: float = 0.0
    uptime_seconds: float = 0.0


class VoicePipeline:
    """Complete voice interaction pipeline for JARVIS.

    Manages the full lifecycle from wake word detection through
    command processing to spoken response, with automatic interrupt
    handling for natural conversation flow.

    Architecture:
        The pipeline runs an async event loop that:
        1. Captures audio from the microphone
        2. Processes it through noise reduction
        3. Runs VAD to detect speech/silence
        4. During wake-word listening: checks for activation phrase
        5. During command listening: accumulates speech, transcribes
        6. Sends transcription to the command handler
        7. Speaks the response, yielding if user interrupts

    Example:
        async def handle(text: str) -> str:
            return f"You said: {text}"

        pipeline = VoicePipeline(settings)
        await pipeline.initialize()
        await pipeline.run(command_handler=handle)
    """

    def __init__(self, settings: VoiceSettings):
        self._settings = settings
        self._state = PipelineState.BOOTING
        self._metrics = PipelineMetrics()
        self._start_time = 0.0

        # Core components (initialized in initialize())
        self._audio_processor: AudioProcessor | None = None
        self._vad: VoiceActivityDetector | None = None
        self._stt: WhisperSTT | None = None
        self._tts: TTSEngine | None = None
        self._wake_word: WakeWordDetector | None = None
        self._mic: MicrophoneManager | None = None
        self._logger: VoiceLogger | None = None

        # State management
        self._command_handler: CommandHandler | None = None
        self._running = False
        self._interrupt_event = asyncio.Event()
        self._wake_event = asyncio.Event()

        # Speech accumulation
        self._speech_buffer: list[np.ndarray] = []
        self._command_audio_chunks: int = 0

        # Continuous listening
        self._continuous = settings.continuous_listening
        self._conversation_turns = 0
        self._max_conversation_turns = 50  # auto-reset after this many

    async def initialize(self) -> None:
        """Initialize all pipeline components.

        Components are initialized in dependency order to handle
        potential model loading and resource allocation.
        """
        logger.info("VoicePipeline initializing...")

        # Audio processor (lightweight, no model loading)
        self._audio_processor = AudioProcessor(self._settings)

        # VAD
        self._vad = VoiceActivityDetector(self._settings)
        self._vad.initialize()

        # STT (loads Whisper model — may take a few seconds)
        self._stt = WhisperSTT(self._settings)
        await self._stt.initialize()

        # TTS
        self._tts = TTSEngine(self._settings)
        await self._tts.initialize()

        # Wake word detector
        self._wake_word = WakeWordDetector(self._settings, vad=self._vad, stt=self._stt)
        await self._wake_word.initialize()

        # Microphone
        self._mic = MicrophoneManager(self._settings, processor=self._audio_processor)
        await self._mic.initialize()

        # Voice logger
        self._logger = VoiceLogger(self._settings)
        await self._logger.initialize()

        self._state = PipelineState.IDLE
        logger.info("VoicePipeline initialized — all systems nominal")

    async def run(self, command_handler: CommandHandler | None = None) -> None:
        """Start the main voice interaction loop.

        This is the primary entry point. It runs until shutdown is
        requested or an unhandled exception occurs.

        Args:
            command_handler: Async callable that receives transcribed text
                and returns a response string. If None, a default echo
                handler is used.
        """
        self._command_handler = command_handler or self._default_handler
        self._running = True
        self._start_time = time.monotonic()

        if self._settings.wake_word_enabled:
            self._state = PipelineState.LISTENING_FOR_WAKE
        else:
            self._state = PipelineState.LISTENING_FOR_COMMAND

        await self._logger.start_session()
        logger.info("VoicePipeline loop started")

        try:
            async for frame in self._mic.stream():
                if not self._running:
                    break

                self._metrics.frames_processed += 1

                # Process audio through the pipeline
                audio_float32 = self._bytes_to_float32(frame.data)

                if audio_float32 is None or len(audio_float32) == 0:
                    continue

                # Route to current state handler
                if self._state == PipelineState.LISTENING_FOR_WAKE:
                    await self._handle_wake_listening(audio_float32)

                elif self._state == PipelineState.LISTENING_FOR_COMMAND:
                    await self._handle_command_listening(audio_float32)

                elif self._state == PipelineState.SPEAKING:
                    # Check for interrupt during speech
                    if self._settings.interrupt_speech:
                        await self._check_interrupt(audio_float32)

        except asyncio.CancelledError:
            logger.info("VoicePipeline cancelled")
        except Exception as exc:
            logger.error("VoicePipeline error: %s", exc, exc_info=True)
        finally:
            await self.shutdown()

    async def _handle_wake_listening(self, audio: np.ndarray) -> None:
        """Process audio when waiting for the wake word."""
        detected = await self._wake_word.process_frame(audio)
        if detected:
            self._metrics.wake_word_detections += 1
            self._state = PipelineState.LISTENING_FOR_COMMAND
            self._speech_buffer.clear()
            self._command_audio_chunks = 0
            self._vad.reset()

            # Play a brief acknowledgment sound (optional)
            logger.info("Wake word detected — listening for command")

    async def _handle_command_listening(self, audio: np.ndarray) -> None:
        """Process audio when listening for a command after wake word."""
        # Run VAD
        event = self._vad.update(audio)

        if event == VADEvent.SPEECH_START or event == VADEvent.SPEECH_CONTINUE:
            # Accumulate speech audio
            self._speech_buffer.append(audio)
            self._command_audio_chunks += 1

            # Check max duration
            total_samples = sum(len(c) for c in self._speech_buffer)
            max_samples = int(self._settings.max_record_seconds * self._settings.mic_sample_rate)
            if total_samples >= max_samples:
                await self._process_command()

        elif event == VADEvent.SPEECH_END:
            # User finished speaking — process the command
            if self._speech_buffer:
                await self._process_command()

        elif event == VADEvent.SILENCE:
            # Check if we had accumulated speech (timeout scenario)
            if self._speech_buffer:
                silence_frames = self._vad.state.consecutive_silence_frames
                max_silence = int(
                    self._settings.silence_timeout_seconds
                    * self._settings.mic_sample_rate
                    / 512  # VAD window size
                )
                if silence_frames >= max_silence:
                    await self._process_command()

    async def _check_interrupt(self, audio: np.ndarray) -> None:
        """Check if user started speaking while JARVIS is talking."""
        if not self._settings.interrupt_speech:
            return

        is_speech = self._vad.is_speech(audio)
        if is_speech:
            # User is speaking — interrupt TTS
            logger.info("Interrupt detected — stopping speech")
            self._tts.interrupt()
            self._interrupt_event.set()
            self._metrics.interrupts += 1
            self._state = PipelineState.INTERRUPTED

    async def _process_command(self) -> None:
        """Transcribe accumulated speech and execute the command."""
        if not self._speech_buffer:
            return

        self._state = PipelineState.PROCESSING
        start_time = time.monotonic()

        # Concatenate all speech audio
        combined_audio = np.concatenate(self._speech_buffer)
        audio_duration_ms = len(combined_audio) / self._settings.mic_sample_rate * 1000
        self._speech_buffer.clear()

        # Transcribe
        stt_start = time.monotonic()
        text = await self._stt.transcribe(combined_audio, self._settings.mic_sample_rate)
        stt_latency_ms = (time.monotonic() - stt_start) * 1000

        if not text or not text.strip():
            logger.debug("No speech recognized")
            self._return_to_listening()
            return

        logger.info("User: '%s' (STT: %.0fms)", text, stt_latency_ms)

        # Log user turn
        await self._logger.log_turn(
            text=text,
            role="user",
            duration_ms=audio_duration_ms,
            latency_ms=stt_latency_ms,
            audio_samples=len(combined_audio),
        )

        # Execute command
        command_start = time.monotonic()
        try:
            response = await self._command_handler(text)
        except Exception as exc:
            logger.error("Command handler error: %s", exc)
            response = "I encountered an error processing your request."

        command_latency_ms = (time.monotonic() - command_start) * 1000

        # Speak response
        if response:
            await self._speak_response(response, text)

        # Update metrics
        total_ms = (time.monotonic() - start_time) * 1000
        self._metrics.commands_processed += 1
        self._metrics.total_speech_ms += audio_duration_ms
        self._metrics.total_processing_ms += total_ms
        self._conversation_turns += 1

        logger.info(
            "Response: '%s' (total: %.0fms, cmd: %.0fms)",
            response[:60] if response else "",
            total_ms,
            command_latency_ms,
        )

        self._return_to_listening()

    async def _speak_response(self, text: str, user_text: str = "") -> None:
        """Speak the response with interrupt support."""
        self._state = PipelineState.SPEAKING
        tts_start = time.monotonic()

        # Pause microphone while speaking (prevents echo)
        if self._mic:
            self._mic.pause()

        try:
            self._interrupt_event.clear()
            completed = True

            async for audio_chunk in self._tts.speak(text, interruptible=True):
                # Check for interrupt between chunks
                if self._interrupt_event.is_set():
                    completed = False
                    break

                # In a real implementation, play audio_chunk here
                # For now, we just yield it
                pass

            tts_latency_ms = (time.monotonic() - tts_start) * 1000
            self._metrics.total_tts_ms += tts_latency_ms

            # Log JARVIS turn
            await self._logger.log_turn(
                text=text,
                role="jarvis",
                latency_ms=tts_latency_ms,
                metadata={"user_trigger": user_text, "completed": completed},
            )

        finally:
            # Resume microphone
            if self._mic:
                self._mic.resume()

    def _return_to_listening(self) -> None:
        """Return to the appropriate listening state."""
        if self._settings.wake_word_enabled:
            self._state = PipelineState.LISTENING_FOR_WAKE
        else:
            self._state = PipelineState.LISTENING_FOR_COMMAND

    @staticmethod
    def _bytes_to_float32(data: bytes) -> Optional[np.ndarray]:
        """Convert raw PCM bytes to float32 numpy array."""
        if not data or len(data) < 2:
            return None
        num_samples = len(data) // 2
        int16_data = np.frombuffer(data[:num_samples * 2], dtype=np.int16)
        return int16_data.astype(np.float32) / 32768.0

    @staticmethod
    async def _default_handler(text: str) -> str:
        """Default command handler (echo)."""
        return f"I heard: {text}"

    async def shutdown(self) -> None:
        """Gracefully shut down the pipeline and release resources."""
        logger.info("VoicePipeline shutting down...")
        self._running = False
        self._state = PipelineState.SHUTDOWN

        await self._logger.end_session()

        if self._mic:
            await self._mic.stop()
        if self._tts:
            await self._tts.cleanup()
        if self._stt:
            await self._stt.cleanup()

        # Log final metrics
        self._metrics.uptime_seconds = time.monotonic() - self._start_time
        if self._metrics.commands_processed > 0:
            self._metrics.average_roundtrip_ms = (
                self._metrics.total_processing_ms / self._metrics.commands_processed
            )
        if self._metrics.frames_processed > 0:
            logger.info("Pipeline metrics: %s", self._metrics)

        logger.info("VoicePipeline shut down")

    # ── Public control methods ───────────────────────────────────────────

    async def interrupt(self) -> None:
        """Manually interrupt the current TTS playback."""
        if self._state == PipelineState.SPEAKING:
            self._tts.interrupt()
            self._interrupt_event.set()
            self._metrics.interrupts += 1

    def pause_listening(self) -> None:
        """Pause the listening loop."""
        if self._mic:
            self._mic.pause()

    def resume_listening(self) -> None:
        """Resume the listening loop."""
        if self._mic:
            self._mic.resume()

    async def calibrate(self, duration_seconds: float = 3.0) -> bool:
        """Run microphone calibration to learn the noise floor.

        Args:
            duration_seconds: How long to sample background noise.

        Returns:
            True if calibration succeeded.
        """
        self._audio_processor.start_calibration()
        self._mic.resume()

        await asyncio.sleep(duration_seconds)

        success = self._audio_processor.stop_calibration()
        logger.info("Calibration %s", "succeeded" if success else "failed")
        return success

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def metrics(self) -> PipelineMetrics:
        self._metrics.uptime_seconds = time.monotonic() - self._start_time
        return self._metrics

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        """Return comprehensive pipeline status."""
        return {
            "state": self._state.name,
            "running": self._running,
            "uptime_seconds": round(time.monotonic() - self._start_time, 1),
            "conversation_turns": self._conversation_turns,
            "wake_word_enabled": self._settings.wake_word_enabled,
            "continuous_listening": self._continuous,
            "interrupt_enabled": self._settings.interrupt_speech,
            "metrics": {
                "frames": self._metrics.frames_processed,
                "wake_detections": self._metrics.wake_word_detections,
                "commands": self._metrics.commands_processed,
                "interrupts": self._metrics.interrupts,
                "avg_roundtrip_ms": round(self._metrics.average_roundtrip_ms, 1),
            },
            "stt": self._stt.stats if self._stt else None,
            "tts": self._tts.stats if self._tts else None,
            "mic": self._mic.stats if self._mic else None,
            "vad": {
                "speaking": self._vad.is_currently_speaking if self._vad else False,
            },
        }
