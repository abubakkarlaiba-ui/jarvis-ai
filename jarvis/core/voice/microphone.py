"""
Microphone input manager for JARVIS.
=====================================
Provides async audio capture from the system microphone with
device selection, format conversion, and chunked streaming.

Uses PyAudio for low-level audio I/O, wrapped in an async-friendly
interface that yields audio chunks without blocking the event loop.

Usage:
    mic = MicrophoneManager(settings)
    await mic.initialize()
    async for chunk in mic.stream():
        process(chunk)
"""

from __future__ import annotations

import asyncio
import logging
import queue
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import numpy as np

from jarvis.config.settings import VoiceSettings
from jarvis.core.voice.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)


@dataclass
class MicrophoneDevice:
    """Information about an available audio input device."""
    index: int
    name: str
    channels: int
    sample_rate: int
    is_default: bool = False


@dataclass
class AudioFrame:
    """A single captured audio frame with metadata."""
    data: bytes
    raw_pcm: bytes
    sample_rate: int
    channels: int
    timestamp: float
    frame_number: int
    duration_ms: float = 0.0


class MicrophoneManager:
    """Async microphone manager with device selection and streaming.

    Captures audio in a background thread and exposes it via an async
    queue that consumers can iterate over.

    Features:
        - Device enumeration and selection
        - Configurable sample rate and channels
        - Background capture thread (non-blocking)
        - Automatic gain adjustment
        - Stream pause/resume for interrupt support

    Example:
        mic = MicrophoneManager(settings)
        await mic.initialize()
        async for frame in mic.stream():
            vad_result = vad.update(frame.data)
    """

    def __init__(self, settings: VoiceSettings, processor: AudioProcessor | None = None):
        self._settings = settings
        self._processor = processor
        self._pyaudio = None
        self._stream = None
        self._device_index = settings.mic_device_index
        self._sample_rate = settings.mic_sample_rate
        self._channels = settings.mic_channels
        self._chunk_size = settings.mic_chunk_size
        self._format = None

        self._frame_queue: asyncio.Queue[AudioFrame] = asyncio.Queue(maxsize=100)
        self._capture_thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._frame_number = 0
        self._pyaudio_lock = threading.Lock()

        # Circular buffer for recent audio (for lookback/interrupt)
        self._lookback_buffer: deque[bytes] = deque(maxlen=50)
        self._lookback_seconds = 2.0

    async def initialize(self) -> None:
        """Initialize PyAudio and open the microphone stream."""
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            self._format = pyaudio.paInt16

            # Resolve device
            if self._device_index is None:
                self._device_index = self._pyaudio.get_default_input_device_info()["index"]
                logger.info("Using default input device")
            else:
                device_info = self._pyaudio.get_device_info_by_index(self._device_index)
                logger.info("Using input device: %s", device_info.get("name", "unknown"))

            # Open stream
            with self._pyaudio_lock:
                self._stream = self._pyaudio.open(
                    format=self._format,
                    channels=self._channels,
                    rate=self._sample_rate,
                    input=True,
                    input_device_index=self._device_index,
                    frames_per_buffer=self._chunk_size,
                    stream_callback=None,
                )

            self._running = True
            logger.info(
                "Microphone initialized (device=%s, rate=%d, channels=%d, chunk=%d)",
                self._device_index,
                self._sample_rate,
                self._channels,
                self._chunk_size,
            )

        except ImportError:
            logger.error("PyAudio not installed. Run: pip install pyaudio")
            raise
        except Exception as exc:
            logger.error("Failed to initialize microphone: %s", exc)
            raise

    def _capture_loop(self) -> None:
        """Background thread that reads audio from the microphone."""
        logger.debug("Capture thread started")
        while self._running:
            if self._paused:
                time.sleep(0.01)
                continue

            try:
                with self._pyaudio_lock:
                    if self._stream is None:
                        break
                    raw_data = self._stream.read(self._chunk_size, exception_on_overflow=False)

                timestamp = time.monotonic()
                self._frame_number += 1

                # Store in lookback buffer
                self._lookback_buffer.append(raw_data)

                # Apply audio processing if available
                processed = raw_data
                if self._processor:
                    processed_pcm = self._processor.process_to_pcm(raw_data)
                    if processed_pcm:
                        processed = processed_pcm

                frame = AudioFrame(
                    data=processed,
                    raw_pcm=raw_data,
                    sample_rate=self._sample_rate,
                    channels=self._channels,
                    timestamp=timestamp,
                    frame_number=self._frame_number,
                    duration_ms=len(processed) / (self._sample_rate * 2) * 1000,
                )

                try:
                    self._frame_queue.put_nowait(frame)
                except asyncio.QueueFull:
                    # Drop oldest frame if queue is full
                    try:
                        self._frame_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    self._frame_queue.put_nowait(frame)

            except Exception as exc:
                if self._running:
                    logger.error("Capture error: %s", exc)
                time.sleep(0.01)

        logger.debug("Capture thread stopped")

    async def stream(self) -> AsyncIterator[AudioFrame]:
        """Async iterator yielding audio frames from the microphone.

        Yields:
            AudioFrame objects containing processed audio data.
        """
        if not self._running:
            await self.initialize()

        # Start capture thread if not running
        if self._capture_thread is None or not self._capture_thread.is_alive():
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="jarvis-mic-capture",
            )
            self._capture_thread.start()

        while self._running:
            try:
                frame = await asyncio.wait_for(self._frame_queue.get(), timeout=0.1)
                yield frame
            except asyncio.TimeoutError:
                continue

    async def read_chunk(self) -> Optional[AudioFrame]:
        """Read a single audio frame (non-iterating mode).

        Returns:
            AudioFrame or None if timeout.
        """
        if not self._running:
            await self.initialize()

        if self._capture_thread is None or not self._capture_thread.is_alive():
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="jarvis-mic-capture",
            )
            self._capture_thread.start()

        try:
            return await asyncio.wait_for(self._frame_queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            return None

    def pause(self) -> None:
        """Pause audio capture (e.g., while JARVIS is speaking)."""
        self._paused = True
        logger.debug("Microphone paused")

    def resume(self) -> None:
        """Resume audio capture after a pause."""
        self._paused = False
        # Flush stale frames
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.debug("Microphone resumed")

    def get_lookback_audio(self, seconds: float = 1.0) -> bytes:
        """Return recent audio from the lookback buffer.

        Useful for capturing audio that preceded a wake word detection
        or interrupt event.

        Args:
            seconds: How many seconds of lookback audio to return.

        Returns:
            Raw PCM bytes of the lookback audio.
        """
        bytes_per_second = self._sample_rate * 2  # 16-bit mono
        target_bytes = int(seconds * bytes_per_second)
        chunks = []
        total = 0

        for chunk in reversed(self._lookback_buffer):
            chunks.append(chunk)
            total += len(chunk)
            if total >= target_bytes:
                break

        chunks.reverse()
        return b"".join(chunks)

    async def stop(self) -> None:
        """Stop capture and release resources."""
        self._running = False
        self._paused = False

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)

        with self._pyaudio_lock:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            if self._pyaudio:
                try:
                    self._pyaudio.terminate()
                except Exception:
                    pass
                self._pyaudio = None

        logger.info("Microphone stopped")

    @staticmethod
    def list_devices() -> list[MicrophoneDevice]:
        """Enumerate available audio input devices.

        Returns:
            List of MicrophoneDevice descriptors.
        """
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            devices = []
            default_index = pa.get_default_input_device_info()["index"]

            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    devices.append(MicrophoneDevice(
                        index=i,
                        name=info.get("name", f"Device {i}"),
                        channels=info.get("maxInputChannels", 1),
                        sample_rate=int(info.get("defaultSampleRate", 16000)),
                        is_default=(i == default_index),
                    ))

            pa.terminate()
            return devices

        except Exception as exc:
            logger.error("Failed to list audio devices: %s", exc)
            return []

    @property
    def is_active(self) -> bool:
        return self._running and not self._paused

    @property
    def stats(self) -> dict:
        return {
            "running": self._running,
            "paused": self._paused,
            "frames_captured": self._frame_number,
            "queue_size": self._frame_queue.qsize(),
            "device_index": self._device_index,
            "sample_rate": self._sample_rate,
        }
