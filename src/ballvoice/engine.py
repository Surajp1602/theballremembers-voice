"""Speech synthesis: Kokoro-82M through kokoro-onnx, with our markup on top.

The phonemizer (espeak-ng) works without the model files, so checking a
script and converting respellings never needs the 300 MB download. Only
`VoiceEngine` loads the model.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

from . import audio as au
from .config import Config
from .markup import Pause, Phonemes, Text, parse
from .models import require
from .voices import blend_style, check_names

PUNCTUATION_START = tuple(",.;:!?…—)")

# kokoro-onnx and phonemizer are chatty at INFO level
for _name in ("kokoro-onnx", "kokoro_onnx", "phonemizer"):
    logging.getLogger(_name).setLevel(logging.ERROR)


@lru_cache(maxsize=1)
def _tokenizer():
    from kokoro_onnx.tokenizer import Tokenizer

    return Tokenizer()


@lru_cache(maxsize=4096)
def _phonemize_cached(text: str, lang: str) -> str:
    return _tokenizer().phonemize(text, lang)


def phonemize(text: str, lang: str = "en-gb") -> str:
    """espeak-ng's phonemes for plain text, limited to what Kokoro knows."""
    text = text.strip()
    if not text:
        return ""
    return _phonemize_cached(text, lang)


def vocab() -> dict:
    return _tokenizer().vocab


def unknown_symbols(phonemes: str) -> set[str]:
    """Characters in a hand-written override the model cannot say."""
    known = vocab()
    return {ch for ch in phonemes if ch not in known}


def _join(parts: list[str]) -> str:
    out = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if out and not part.startswith(PUNCTUATION_START):
            out += " "
        out += part
    return out


def to_phoneme_groups(text: str, lang: str) -> list[str | float]:
    """Turn marked-up text into phoneme strings, with pauses (seconds) between."""
    known = vocab()
    groups: list[str | float] = []
    current: list[str] = []

    def flush() -> None:
        joined = _join(current)
        # A group of only punctuation would make the model produce noise
        if any(ch.isalpha() for ch in joined):
            groups.append(joined)
        current.clear()

    for segment in parse(text):
        if isinstance(segment, Pause):
            flush()
            groups.append(segment.seconds)
        elif isinstance(segment, Text):
            current.append(phonemize(segment.text, lang))
        elif isinstance(segment, Phonemes):
            current.append("".join(ch for ch in segment.phonemes if ch in known))
    flush()
    return groups


class VoiceEngine:
    def __init__(self, config: Config):
        require(config.models_dir)
        from kokoro_onnx import Kokoro

        self.config = config
        self.kokoro = Kokoro(str(config.model_path), str(config.voices_path))
        self._styles: dict[str, np.ndarray] = {}

    @property
    def voice_names(self) -> list[str]:
        return self.kokoro.get_voices()

    def style(self, spec: str) -> np.ndarray:
        if spec not in self._styles:
            check_names(spec, self.voice_names)
            styles = {name: self.kokoro.get_voice_style(name) for name in self.voice_names}
            self._styles[spec] = blend_style(spec, styles)
        return self._styles[spec]

    def synth(self, text: str, voice: str, speed: float | None = None, lang: str | None = None) -> np.ndarray:
        """Speak one line of marked-up text. Returns float32 audio at 24 kHz."""
        speed = self.config.speed if speed is None else speed
        lang = lang or self.config.lang
        style = self.style(voice)

        parts: list[np.ndarray] = []
        for group in to_phoneme_groups(text, lang):
            if isinstance(group, float):
                parts.append(au.silence(group))
                continue
            audio, _ = self.kokoro.create(
                group,
                voice=style,
                speed=speed,
                lang=lang,
                is_phonemes=True,
                trim=True,
                sentence_pause=self.config.sentence_pause,
                clause_pause=self.config.clause_pause,
            )
            parts.append(np.asarray(audio, dtype=np.float32))

        if not parts:
            return au.silence(0)
        return np.concatenate(parts).astype(np.float32)
