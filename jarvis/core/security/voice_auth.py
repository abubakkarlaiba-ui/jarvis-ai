"""
Security module — voice-based authentication using voice prints.
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path
from typing import Any

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore
    _HAS_NUMPY = False

_DATA_DIR = Path("./data/security/voice")
_CONFIDENCE_THRESHOLD = 0.85
_SAMPLE_RATE = 16000
_NUM_MFCC = 13
_FFT_SIZE = 512
_HOP_LENGTH = 256
_NUM_FILTERS = 26


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _mel_filterbank(sample_rate: int, n_fft: int, n_filters: int) -> list[list[float]]:
    low_freq = 0
    high_freq = sample_rate / 2
    low_mel = 2595 * math.log10(1 + low_freq / 700)
    high_mel = 2595 * math.log10(1 + high_freq / 700)
    mel_points = [low_mel + i * (high_mel - low_mel) / (n_filters + 1) for i in range(n_filters + 2)]
    hz_points = [700 * (10 ** (m / 2595) - 1) for m in mel_points]
    bin_points = [int(round((n_fft + 1) * f / sample_rate)) for f in hz_points]

    filters = []
    for i in range(n_filters):
        filt = [0.0] * (n_fft // 2 + 1)
        left = bin_points[i]
        center = bin_points[i + 1]
        right = bin_points[i + 2]
        for j in range(left, center):
            if center != left:
                filt[j] = (j - left) / (center - left)
        for j in range(center, right):
            if right != center:
                filt[j] = (right - j) / (right - center)
        filters.append(filt)
    return filters


def _dct_matrix(n: int) -> list[list[float]]:
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(math.cos(math.pi * i * (2 * j + 1) / (2 * n)))
        matrix.append(row)
    return matrix


class VoiceAuth:
    def __init__(self, data_dir: str = "./data/security/voice") -> None:
        self._data_dir = Path(data_dir)
        _ensure_dir(self._data_dir)

    # ── public API ───────────────────────────────────────────────
    async def enroll(self, user_id: str, audio_samples: list[bytes]) -> bool:
        if not audio_samples:
            return False
        all_features: list[float] = []
        for sample in audio_samples:
            feats = self._extract_features(sample)
            if feats:
                all_features.extend(feats)
        if not all_features:
            return False
        avg = self._average_features(all_features, len(audio_samples))
        self._save_voice_print(user_id, avg)
        return True

    async def verify(self, user_id: str, audio_sample: bytes) -> tuple[bool, float]:
        stored = self._load_voice_print(user_id)
        if stored is None:
            return False, 0.0
        features = self._extract_features(audio_sample)
        if not features:
            return False, 0.0
        confidence = self._compare_features(stored, features)
        return confidence >= _CONFIDENCE_THRESHOLD, confidence

    def _extract_features(self, audio: bytes) -> list[float]:
        samples = self._decode_audio(audio)
        if not samples or len(samples) < _FFT_SIZE:
            return []

        if _HAS_NUMPY:
            return self._extract_features_numpy(samples)
        return self._extract_features_pure(samples)

    def _extract_features_numpy(self, samples: list[float]) -> list[float]:
        arr = np.array(samples, dtype=np.float64)

        n_frames = (len(arr) - _FFT_SIZE) // _HOP_LENGTH + 1
        if n_frames <= 0:
            return []

        # mel filterbank
        filterbank = _mel_filterbank(_SAMPLE_RATE, _FFT_SIZE, _NUM_FILTERS)
        fb_arr = np.array(filterbank, dtype=np.float64)
        dct_mat = np.array(_dct_matrix(_NUM_FILTERS), dtype=np.float64)[:_NUM_MFCC]

        mfccs = []
        for i in range(n_frames):
            start = i * _HOP_LENGTH
            frame = arr[start: start + _FFT_SIZE]
            windowed = frame * np.hanning(_FFT_SIZE)
            spectrum = np.abs(np.fft.rfft(windowed)) ** 2
            mel_energies = np.dot(fb_arr, spectrum)
            mel_energies = np.maximum(mel_energies, 1e-10)
            log_mel = np.log(mel_energies)
            c = np.dot(dct_mat, log_mel)
            mfccs.append(c.tolist())

        # mean-normalize across frames
        if mfccs:
            arr_mfcc = np.array(mfccs)
            means = arr_mfcc.mean(axis=0)
            stds = arr_mfcc.std(axis=0)
            stds = np.maximum(stds, 1e-10)
            arr_mfcc = (arr_mfcc - means) / stds
            return arr_mfcc.mean(axis=0).tolist()
        return []

    def _extract_features_pure(self, samples: list[float]) -> list[float]:
        n_frames = (len(samples) - _FFT_SIZE) // _HOP_LENGTH + 1
        if n_frames <= 0:
            return []

        filterbank = _mel_filterbank(_SAMPLE_RATE, _FFT_SIZE, _NUM_FILTERS)
        dct_mat = _dct_matrix(_NUM_FILTERS)[:_NUM_MFCC]

        mfccs: list[list[float]] = []
        for i in range(n_frames):
            start = i * _HOP_LENGTH
            frame = samples[start: start + _FFT_SIZE]
            # simple DFT magnitude
            spectrum = []
            for k in range(_FFT_SIZE // 2 + 1):
                real = sum(frame[n] * math.cos(2 * math.pi * k * n / _FFT_SIZE) for n in range(_FFT_SIZE))
                imag = sum(frame[n] * math.sin(2 * math.pi * k * n / _FFT_SIZE) for n in range(_FFT_SIZE))
                spectrum.append(real * real + imag * imag)
            # mel energies
            mel_energies = []
            for fb in filterbank:
                energy = sum(s * f for s, f in zip(spectrum, fb))
                mel_energies.append(max(energy, 1e-10))
            log_mel = [math.log(e) for e in mel_energies]
            # DCT
            c = [sum(row[j] * log_mel[j] for j in range(len(log_mel))) for row in dct_mat]
            mfccs.append(c)

        if mfccs:
            n_mfcc = len(mfccs[0])
            means = [sum(f[k] for f in mfccs) / len(mfccs) for k in range(n_mfcc)]
            stds = []
            for k in range(n_mfcc):
                var = sum((f[k] - means[k]) ** 2 for f in mfccs) / len(mfccs)
                stds.append(max(math.sqrt(var), 1e-10))
            normalized = [[(f[k] - means[k]) / stds[k] for k in range(n_mfcc)] for f in mfccs]
            return [sum(f[k] for f in normalized) / len(normalized) for k in range(n_mfcc)]
        return []

    def _compare_features(self, features1: list[float], features2: list[float]) -> float:
        if len(features1) != len(features2):
            min_len = min(len(features1), len(features2))
            features1 = features1[:min_len]
            features2 = features2[:min_len]
        if not features1:
            return 0.0
        return _cosine_similarity(features1, features2)

    def _average_features(self, all_features: list[float], n_samples: int) -> list[float]:
        if not all_features or n_samples == 0:
            return []
        chunk_size = len(all_features) // n_samples
        if chunk_size == 0:
            return all_features
        chunks = [all_features[i * chunk_size: (i + 1) * chunk_size] for i in range(n_samples)]
        if _HAS_NUMPY:
            arr = np.array(chunks)
            return arr.mean(axis=0).tolist()
        n_feat = len(chunks[0])
        return [sum(c[k] for c in chunks) / len(chunks) for k in range(n_feat)]

    # ── audio decoding ───────────────────────────────────────────
    def _decode_audio(self, raw: bytes) -> list[float]:
        if len(raw) < 44:
            return []
        # try WAV
        if raw[:4] == b"RIFF":
            return self._decode_wav(raw)
        # raw PCM s16le fallback
        return self._decode_pcm(raw)

    def _decode_wav(self, raw: bytes) -> list[float]:
        try:
            import io
            with wave.open(io.BytesIO(raw), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())
        except Exception:
            return []
        return self._pcm_to_float(frames, sampwidth, n_channels)

    def _decode_pcm(self, raw: bytes) -> list[float]:
        n_samples = len(raw) // 2
        if n_samples == 0:
            return []
        fmt = f"<{n_samples}h"
        if len(raw) < n_samples * 2:
            return []
        ints = struct.unpack(fmt, raw[: n_samples * 2])
        return [s / 32768.0 for s in ints]

    @staticmethod
    def _pcm_to_float(data: bytes, sampwidth: int, n_channels: int) -> list[float]:
        if sampwidth == 2:
            n = len(data) // 2
            ints = struct.unpack(f"<{n}h", data[: n * 2])
            samples = [s / 32768.0 for s in ints]
        elif sampwidth == 3:
            n = len(data) // 3
            samples = []
            for i in range(n):
                b = data[i * 3: i * 3 + 3]
                val = int.from_bytes(b, byteorder="little", signed=True)
                samples.append(val / 8388608.0)
        elif sampwidth == 4:
            n = len(data) // 4
            ints = struct.unpack(f"<{n}i", data[: n * 4])
            samples = [s / 2147483648.0 for s in ints]
        else:
            return []
        if n_channels > 1:
            samples = samples[::n_channels]
        return samples

    # ── persistence ──────────────────────────────────────────────
    def _voice_path(self, user_id: str) -> Path:
        return self._data_dir / f"{user_id}.json"

    def _save_voice_print(self, user_id: str, features: list[float]) -> None:
        path = self._voice_path(user_id)
        _ensure_dir(path.parent)
        path.write_text(json.dumps({"user_id": user_id, "features": features}, indent=2), encoding="utf-8")

    def _load_voice_print(self, user_id: str) -> list[float] | None:
        path = self._voice_path(user_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("features")
        except Exception:
            return None

    def delete_voice_print(self, user_id: str) -> bool:
        path = self._voice_path(user_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_enrolled(self) -> list[str]:
        if not self._data_dir.exists():
            return []
        return [p.stem for p in self._data_dir.glob("*.json")]

    def get_confidence_threshold(self) -> float:
        return _CONFIDENCE_THRESHOLD
