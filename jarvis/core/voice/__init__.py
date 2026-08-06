"""
Voice module — complete voice interaction system for JARVIS.
===========================================================
Provides end-to-end voice interaction with wake word detection,
speech-to-text, text-to-speech, noise reduction, and interrupt support.

Architecture:
    Microphone → AudioProcessor → VAD → WakeWord → STT → Brain → TTS → Speaker
                                                                    ↕
                                                              VoiceLogger

Components:
    - MicrophoneManager: Configurable mic input with device selection
    - AudioProcessor: Noise gate + spectral noise reduction
    - VoiceActivityDetector: Silero VAD for speech/silence detection
    - WakeWordDetector: "Hey Jarvis" detection via fuzzy text matching
    - WhisperSTT: Whisper-based speech-to-text (local or API)
    - TTSEngine: Multi-personality TTS with speed/pitch/volume control
    - VoiceLogger: Conversation logging with latency tracking
    - VoicePipeline: Complete orchestrator with interrupt support

Usage:
    from jarvis.core.voice import VoicePipeline, VoiceSettings

    settings = VoiceSettings()
    pipeline = VoicePipeline(settings)
    await pipeline.initialize()
    await pipeline.run(command_handler=my_handler)
"""

from jarvis.core.voice.module import (
    VoiceModule,
    VoiceState,
    AudioChunk,
    SpeechToText,
    TextToSpeech,
    WakeWordDetector as WakeWordDetectorBase,
)
from jarvis.core.voice.pipeline import VoicePipeline, PipelineState, PipelineMetrics
from jarvis.core.voice.audio_processor import AudioProcessor
from jarvis.core.voice.vad import VoiceActivityDetector, VADEvent
from jarvis.core.voice.microphone import MicrophoneManager, AudioFrame
from jarvis.core.voice.whisper_stt import WhisperSTT
from jarvis.core.voice.tts_engine import (
    TTSEngine,
    VoicePersonality,
    VoiceProfile,
    VOICE_PROFILES,
)
from jarvis.core.voice.wake_word import WakeWordDetector
from jarvis.core.voice.voice_logger import VoiceLogger, VoiceTurn, VoiceSession

__all__ = [
    # Pipeline
    "VoicePipeline",
    "PipelineState",
    "PipelineMetrics",
    # Audio
    "AudioProcessor",
    "AudioFrame",
    # VAD
    "VoiceActivityDetector",
    "VADEvent",
    # Microphone
    "MicrophoneManager",
    # STT
    "WhisperSTT",
    # TTS
    "TTSEngine",
    "VoicePersonality",
    "VoiceProfile",
    "VOICE_PROFILES",
    # Wake word
    "WakeWordDetector",
    # Logger
    "VoiceLogger",
    "VoiceTurn",
    "VoiceSession",
    # Legacy compat
    "VoiceModule",
    "VoiceState",
    "AudioChunk",
    "SpeechToText",
    "TextToSpeech",
    "WakeWordDetectorBase",
]
