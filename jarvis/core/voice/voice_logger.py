"""
Voice conversation logger for JARVIS.
=====================================
Records voice interactions for debugging, analytics, and quality review.

Logs include:
    - Timestamped transcripts (user + JARVIS)
    - Audio duration and processing latency
    - Intent detection results
    - Optional raw audio saving

Logs are stored in JSON (default), CSV, or plain text format.

Usage:
    logger = VoiceLogger(settings)
    await logger.initialize()
    await logger.log_turn("What's the weather?", "Let me check.", latency_ms=342)
    await logger.flush()
"""

from __future__ import annotations

import csv
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from jarvis.config.settings import VoiceSettings
from jarvis.utils.helpers import ensure_directory, utc_now

logger = logging.getLogger(__name__)


@dataclass
class VoiceTurn:
    """A single turn in a voice conversation."""
    turn_id: str
    session_id: str
    timestamp: str
    role: str  # "user" or "jarvis"
    text: str
    duration_ms: float = 0.0
    processing_latency_ms: float = 0.0
    intent: str = ""
    confidence: float = 0.0
    audio_samples: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class VoiceSession:
    """Metadata for a complete voice conversation session."""
    session_id: str
    start_time: str
    end_time: str = ""
    turns: list[VoiceTurn] = field(default_factory=list)
    total_duration_ms: float = 0.0
    total_user_audio_ms: float = 0.0
    total_jarvis_audio_ms: float = 0.0
    average_latency_ms: float = 0.0


class VoiceLogger:
    """Logs voice conversations to disk.

    Supports multiple output formats and optional audio saving.

    Example:
        vlog = VoiceLogger(settings)
        await vlog.initialize()
        await vlog.start_session()
        await vlog.log_turn("Hello", "Hello, sir.", role="user")
        await vlog.log_turn("Hello, sir.", None, role="jarvis", latency_ms=120)
        await vlog.end_session()
    """

    def __init__(self, settings: VoiceSettings):
        self._enabled = settings.voice_log_enabled
        self._log_dir = Path(settings.voice_log_dir)
        self._format = settings.voice_log_format
        self._save_audio = settings.voice_log_audio

        self._session: VoiceSession | None = None
        self._session_id = ""
        self._turn_buffer: list[VoiceTurn] = []
        self._buffer_size = 10  # flush every N turns

        self._csv_writer = None
        self._csv_file = None
        self._jsonl_file = None

    async def initialize(self) -> None:
        """Initialize the logging system."""
        if not self._enabled:
            logger.info("Voice logging disabled")
            return

        ensure_directory(self._log_dir)
        logger.info("VoiceLogger initialized (dir=%s, format=%s)", self._log_dir, self._format)

    async def start_session(self) -> str:
        """Start a new voice conversation session.

        Returns:
            The session ID.
        """
        if not self._enabled:
            return ""

        self._session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self._session = VoiceSession(
            session_id=self._session_id,
            start_time=utc_now().isoformat(),
        )

        # Open log files
        session_dir = ensure_directory(self._log_dir / self._session_id)

        if self._format == "json":
            self._jsonl_file = open(session_dir / "transcript.jsonl", "w", encoding="utf-8")
        elif self._format == "csv":
            self._csv_file = open(session_dir / "transcript.csv", "w", newline="", encoding="utf-8")
            self._csv_writer = csv.writer(self._csv_file)
            self._csv_writer.writerow([
                "turn_id", "timestamp", "role", "text", "duration_ms",
                "latency_ms", "intent", "confidence",
            ])

        logger.info("Voice session started: %s", self._session_id)
        return self._session_id

    async def log_turn(
        self,
        text: str,
        role: str,
        duration_ms: float = 0.0,
        latency_ms: float = 0.0,
        intent: str = "",
        confidence: float = 0.0,
        audio_samples: int = 0,
        metadata: dict | None = None,
    ) -> None:
        """Log a single conversation turn.

        Args:
            text: The spoken text.
            role: "user" or "jarvis".
            duration_ms: Audio duration in milliseconds.
            latency_ms: Processing latency in milliseconds.
            intent: Detected intent name.
            confidence: Intent confidence score.
            audio_samples: Number of audio samples processed.
            metadata: Additional metadata.
        """
        if not self._enabled or not self._session:
            return

        turn = VoiceTurn(
            turn_id=str(uuid.uuid4()),
            session_id=self._session_id,
            timestamp=utc_now().isoformat(),
            role=role,
            text=text,
            duration_ms=duration_ms,
            processing_latency_ms=latency_ms,
            intent=intent,
            confidence=confidence,
            audio_samples=audio_samples,
            metadata=metadata or {},
        )

        self._turn_buffer.append(turn)
        self._session.turns.append(turn)

        # Update session stats
        if role == "user":
            self._session.total_user_audio_ms += duration_ms
        else:
            self._session.total_jarvis_audio_ms += duration_ms

        # Flush if buffer is full
        if len(self._turn_buffer) >= self._buffer_size:
            await self.flush()

    async def log_audio(self, audio: np.ndarray, label: str = "raw") -> None:
        """Save raw audio to the current session directory.

        Args:
            audio: Float32 audio array.
            label: Label for the audio file.
        """
        if not self._enabled or not self._save_audio or not self._session:
            return

        session_dir = self._log_dir / self._session_id
        if not session_dir.exists():
            return

        # Save as WAV
        filename = f"{label}_{len(os.listdir(session_dir))}.wav"
        filepath = session_dir / filename

        try:
            import wave
            int16_audio = (audio * 32767).clip(-32768, 32767).astype(np.int16)
            with wave.open(str(filepath), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(int16_audio.tobytes())
        except Exception as exc:
            logger.error("Failed to save audio: %s", exc)

    async def flush(self) -> None:
        """Flush buffered turns to disk."""
        if not self._turn_buffer:
            return

        for turn in self._turn_buffer:
            try:
                if self._jsonl_file:
                    self._jsonl_file.write(json.dumps(asdict(turn)) + "\n")

                if self._csv_writer:
                    self._csv_writer.writerow([
                        turn.turn_id,
                        turn.timestamp,
                        turn.role,
                        turn.text,
                        f"{turn.duration_ms:.1f}",
                        f"{turn.processing_latency_ms:.1f}",
                        turn.intent,
                        f"{turn.confidence:.3f}",
                    ])
            except Exception as exc:
                logger.error("Failed to write turn log: %s", exc)

        self._turn_buffer.clear()

        if self._jsonl_file:
            self._jsonl_file.flush()

    async def end_session(self) -> VoiceSession | None:
        """End the current session and write final summary.

        Returns:
            The completed VoiceSession, or None if logging is disabled.
        """
        if not self._enabled or not self._session:
            return None

        # Flush remaining turns
        await self.flush()

        self._session.end_time = utc_now().isoformat()

        # Calculate stats
        if self._session.turns:
            latencies = [t.processing_latency_ms for t in self._session.turns if t.processing_latency_ms > 0]
            self._session.average_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

        total_turns = len(self._session.turns)
        user_turns = sum(1 for t in self._session.turns if t.role == "user")

        # Write session summary
        summary_path = self._log_dir / self._session_id / "session_summary.json"
        try:
            summary = {
                "session_id": self._session.session_id,
                "start_time": self._session.start_time,
                "end_time": self._session.end_time,
                "total_turns": total_turns,
                "user_turns": user_turns,
                "jarvis_turns": total_turns - user_turns,
                "total_user_audio_ms": round(self._session.total_user_audio_ms, 1),
                "total_jarvis_audio_ms": round(self._session.total_jarvis_audio_ms, 1),
                "average_latency_ms": round(self._session.average_latency_ms, 1),
            }
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to write session summary: %s", exc)

        # Close files
        if self._jsonl_file:
            self._jsonl_file.close()
            self._jsonl_file = None
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None

        session = self._session
        logger.info(
            "Voice session ended: %s (%d turns, avg_latency=%.1fms)",
            session.session_id,
            total_turns,
            session.average_latency_ms,
        )

        self._session = None
        self._session_id = ""
        return session

    def get_stats(self) -> dict:
        """Return logging statistics."""
        if self._session:
            return {
                "enabled": self._enabled,
                "session_id": self._session_id,
                "turns_logged": len(self._session.turns),
                "buffer_size": len(self._turn_buffer),
            }
        return {"enabled": self._enabled, "session_id": None, "turns_logged": 0}
