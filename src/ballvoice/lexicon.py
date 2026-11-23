"""The channel lexicon: names the ball has learned to say, kept across videos.

It uses the same shape as the `pronunciations` list in PRODUCTION_JSON, so an
entry can be copied between the two. When both have the same word, the
production's entry wins for that video.
"""

from __future__ import annotations

import json
from pathlib import Path

from .markup import Pronunciation


def load_lexicon(path: Path) -> list[Pronunciation]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from None
    items = data.get("pronunciations", []) if isinstance(data, dict) else data
    return [Pronunciation.from_dict(item) for item in items if isinstance(item, dict)]


def save_lexicon(path: Path, entries: list[Pronunciation]) -> None:
    entries = sorted(entries, key=lambda e: e.word.lower())
    data = {"pronunciations": [e.to_dict() for e in entries]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge(*lists: list[Pronunciation]) -> list[Pronunciation]:
    """Later lists win for the same word (case-insensitive)."""
    merged: dict[str, Pronunciation] = {}
    for entries in lists:
        for entry in entries:
            if entry.word:
                merged[entry.word.lower()] = entry
    return list(merged.values())


def upsert(entries: list[Pronunciation], new: Pronunciation) -> tuple[list[Pronunciation], bool]:
    """Add or replace an entry. Returns the list and whether it replaced one."""
    kept = [e for e in entries if e.word.lower() != new.word.lower()]
    return kept + [new], len(kept) != len(entries)
