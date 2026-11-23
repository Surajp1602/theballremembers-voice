"""Small audio helpers. Kokoro speaks at 24 kHz mono."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24000


def silence(seconds: float) -> np.ndarray:
    return np.zeros(max(0, int(round(seconds * SAMPLE_RATE))), dtype=np.float32)


def seconds(audio: np.ndarray) -> float:
    return len(audio) / SAMPLE_RATE


def pad_tail(audio: np.ndarray, ms: int) -> np.ndarray:
    if ms <= 0:
        return audio
    return np.concatenate([audio, silence(ms / 1000)])


def peak_gain(chunks: list[np.ndarray], peak_dbfs: float, max_gain: float = 4.0) -> float:
    """One gain for every chunk, so the loudest peak lands at `peak_dbfs`.

    The same gain is used for all shots so their loudness stays matched.
    """
    peak = max((float(np.abs(c).max()) for c in chunks if len(c)), default=0.0)
    if peak <= 1e-6:
        return 1.0
    return min(max_gain, (10 ** (peak_dbfs / 20)) / peak)


def write_wav(path: Path, audio: np.ndarray, subtype: str = "PCM_16") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(audio, -1.0, 1.0), SAMPLE_RATE, subtype=subtype)


def read_wav(path: Path) -> np.ndarray:
    audio, rate = sf.read(str(path), dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if rate != SAMPLE_RATE:
        raise ValueError(f"{path} is {rate} Hz, expected {SAMPLE_RATE} Hz")
    return audio.astype(np.float32)
