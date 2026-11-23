"""Voice names and blends.

A voice is written as one Kokoro voice ("bm_george") or a weighted blend
("bm_george:60,bm_fable:40"). Weights are relative, so 60/40 and 3/2 are the
same blend. Unweighted names in a list are blended equally.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

import numpy as np

ACCENTS = {"a": "American", "b": "British", "e": "Spanish", "f": "French", "h": "Hindi",
           "i": "Italian", "j": "Japanese", "p": "Portuguese", "z": "Mandarin"}
GENDERS = {"f": "female", "m": "male"}

_NAME_RE = re.compile(r"^[a-z]{2}_[a-z0-9]+$")


class VoiceError(ValueError):
    pass


def parse_voice_spec(spec: str) -> list[tuple[str, float]]:
    """'bm_george:60,bm_fable:40' -> [('bm_george', 0.6), ('bm_fable', 0.4)]"""
    parts = [p.strip() for p in str(spec).split(",") if p.strip()]
    if not parts:
        raise VoiceError("No voice given")

    blend: list[tuple[str, float]] = []
    for part in parts:
        name, _, weight_text = part.partition(":")
        name = name.strip()
        if not _NAME_RE.match(name):
            raise VoiceError(
                f"'{name}' doesn't look like a Kokoro voice name (e.g. bm_george)"
            )
        try:
            weight = float(weight_text) if weight_text.strip() else 1.0
        except ValueError:
            raise VoiceError(f"Bad weight in '{part}', use name:number") from None
        if weight <= 0:
            raise VoiceError(f"Weight for {name} must be above zero")
        blend.append((name, weight))

    total = sum(w for _, w in blend)
    return [(name, weight / total) for name, weight in blend]


def check_names(spec: str, available: list[str]) -> None:
    """Raise a helpful error if the blend uses a voice the voices file lacks."""
    for name, _ in parse_voice_spec(spec):
        if name not in available:
            close = difflib.get_close_matches(name, available, n=3)
            hint = f" Did you mean {', '.join(close)}?" if close else ""
            raise VoiceError(f"Voice '{name}' is not in the voices file.{hint}")


def describe(spec: str) -> str:
    """Human-readable form: 'bm_george 60% + bm_fable 40%'."""
    blend = parse_voice_spec(spec)
    if len(blend) == 1:
        return blend[0][0]
    return " + ".join(f"{name} {round(weight * 100)}%" for name, weight in blend)


def slug(spec: str) -> str:
    """File-name-safe form: 'bm_george-60_bm_fable-40'."""
    blend = parse_voice_spec(spec)
    if len(blend) == 1:
        return blend[0][0]
    return "_".join(f"{name}-{round(weight * 100)}" for name, weight in blend)


def blend_style(spec: str, styles: dict[str, np.ndarray]) -> np.ndarray:
    """Mix the style vectors of the voices in `spec` by their weights."""
    blend = parse_voice_spec(spec)
    check_names(spec, list(styles))
    mixed = sum(weight * styles[name].astype(np.float32) for name, weight in blend)
    return np.asarray(mixed, dtype=np.float32)


def list_voices(voices_path: Path) -> list[str]:
    with np.load(voices_path) as data:
        return sorted(data.files)


def label(name: str) -> str:
    accent = ACCENTS.get(name[0], name[0])
    gender = GENDERS.get(name[1], name[1])
    return f"{accent} {gender}"
