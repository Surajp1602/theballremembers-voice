"""Reading PRODUCTION_JSON.

The file can be the bare JSON object, or the whole package the master prompt
returns (Markdown Part A followed by the PRODUCTION_JSON block). In the second
case the first JSON object that has a "shots" list is used.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .markup import Pronunciation


class ProductionError(ValueError):
    pass


@dataclass
class Shot:
    id: str
    start: float | None
    end: float | None
    vo: str
    tts_text: str
    speed: float | None = None
    raw: dict = field(default_factory=dict)

    @property
    def window(self) -> float | None:
        if self.start is None or self.end is None:
            return None
        return self.end - self.start

    @property
    def speaks(self) -> bool:
        return bool(self.tts_text.strip())


@dataclass
class Production:
    path: Path
    data: dict
    video_id: str
    format: str
    title: str
    tts: dict
    hook: dict
    pronunciations: list[Pronunciation]
    shots: list[Shot]

    @property
    def name(self) -> str:
        """Folder name for the outputs."""
        source = self.video_id or self.path.stem
        return re.sub(r"[^A-Za-z0-9._-]+", "-", source).strip("-") or "production"

    @property
    def runtime(self) -> float:
        ends = [s.end for s in self.shots if s.end is not None]
        return max(ends) if ends else 0.0


def _number(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_json(text: str) -> dict:
    """Find the production object in a bare JSON file or a whole package."""
    text = text.lstrip("﻿")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    marker = text.find("PRODUCTION_JSON")
    starts = [m.start() for m in re.finditer(r"\{", text)]
    # Objects after the PRODUCTION_JSON label are tried first
    if marker >= 0:
        starts.sort(key=lambda i: (i < marker, i))
    for start in starts:
        try:
            data, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("shots"), list):
            return data
    raise ProductionError(
        "No PRODUCTION_JSON found: expected a JSON object with a \"shots\" list. "
        "If you pasted the whole package, check the JSON block is complete and valid."
    )


def load_production(path: str | Path) -> Production:
    path = Path(path)
    if not path.exists():
        raise ProductionError(f"File not found: {path}")
    data = extract_json(path.read_text(encoding="utf-8"))

    shots = []
    for index, raw in enumerate(data.get("shots") or []):
        if not isinstance(raw, dict):
            raise ProductionError(f"Shot #{index + 1} is not an object")
        shots.append(
            Shot(
                id=str(raw.get("id") or "").strip(),
                start=_number(raw.get("start")),
                end=_number(raw.get("end")),
                vo=str(raw.get("vo") or ""),
                tts_text=str(raw.get("tts_text") or ""),
                speed=_number(raw.get("tts_speed")),
                raw=raw,
            )
        )

    pronunciations = [
        Pronunciation.from_dict(p)
        for p in data.get("pronunciations") or []
        if isinstance(p, dict)
    ]

    return Production(
        path=path,
        data=data,
        video_id=str(data.get("video_id") or ""),
        format=str(data.get("format") or "").upper(),
        title=str(data.get("title") or ""),
        tts=data.get("tts") if isinstance(data.get("tts"), dict) else {},
        hook=data.get("hook") if isinstance(data.get("hook"), dict) else {},
        pronunciations=pronunciations,
        shots=shots,
    )


def production_voice(production: Production) -> str:
    """The voice the production asks for, if it names a usable one."""
    voice = str(production.tts.get("voice") or "").strip()
    if not voice or "[" in voice or " " in voice:
        return ""  # empty, or still the [KOKORO VOICE ID] placeholder
    return voice
