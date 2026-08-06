import struct


class MockVoiceService:
    def __init__(self) -> None:
        self._transcription = "Mock transcription"
        self._wake_word_detected = False
        self._call_history: list[dict] = []

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        self._call_history.append({"method": "synthesize", "text": text, "voice": voice})
        return self._generate_test_audio(len(text))

    async def transcribe(self, audio: bytes) -> str:
        self._call_history.append({"method": "transcribe", "audio_length": len(audio)})
        return self._transcription

    async def detect_wake_word(self, audio: bytes) -> bool:
        self._call_history.append({"method": "detect_wake_word", "audio_length": len(audio)})
        return self._wake_word_detected

    async def get_vad_level(self, audio: bytes) -> float:
        self._call_history.append({"method": "get_vad_level", "audio_length": len(audio)})
        if len(audio) == 0:
            return 0.0
        return 0.75

    def set_transcription(self, text: str) -> None:
        self._transcription = text

    def set_wake_word_detected(self, detected: bool) -> None:
        self._wake_word_detected = detected

    def get_call_history(self) -> list[dict]:
        return list(self._call_history)

    def reset(self) -> None:
        self._call_history.clear()
        self._transcription = "Mock transcription"
        self._wake_word_detected = False

    @staticmethod
    def _generate_test_audio(length: int) -> bytes:
        num_samples = max(length, 160)
        try:
            import numpy as np

            t = np.linspace(0, num_samples / 16000, num_samples, dtype=np.float32)
            signal = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
            return signal.tobytes()
        except ImportError:
            return struct.pack(f"<{num_samples}h", *([1600] * num_samples))
