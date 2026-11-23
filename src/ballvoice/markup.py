"""The small markup the voice tool understands inside tts_text.

    [pause:0.4]              hold for 0.4 seconds (also [pause:400ms])
    [Panenka](/pˈanɛŋka/)    say this word with these phonemes (Kokoro's own syntax)
    pah-NEN-kah              a respelling: hyphenated syllables, stressed one in CAPS

Names listed in the production's `pronunciations` (or in the channel lexicon)
are turned into the second form automatically, so tts_text can keep the real
spelling of every name.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .respell import RespellingError, respelling_to_ipa

PAUSE_RE = re.compile(r"\[pause\s*:\s*(\d+(?:\.\d+)?)\s*(ms|s)?\s*\]", re.IGNORECASE)
OVERRIDE_RE = re.compile(r"\[([^\[\]]+)\]\(/([^/()]*)/\)")
MARKUP_RE = re.compile(f"{PAUSE_RE.pattern}|{OVERRIDE_RE.pattern}", re.IGNORECASE)
RESPELLING_RE = re.compile(r"(?<![\w-])([A-Za-z]+(?:-[A-Za-z]+)+)(?![\w-])")

# Upper-case words that turn up hyphenated in football scripts and are not respellings
ACRONYMS = {"VAR", "UEFA", "FIFA", "TV", "UK", "USA", "EU", "PSG", "MLS", "GOAT", "OK"}

MAX_PAUSE_SECONDS = 5.0


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Phonemes:
    phonemes: str
    word: str


@dataclass(frozen=True)
class Pause:
    seconds: float


Segment = Text | Phonemes | Pause


class MarkupError(ValueError):
    """tts_text contains markup the tool does not understand."""


@dataclass
class Pronunciation:
    """How to say one word or name. `ipa` wins over `say_as` when both are set."""

    word: str
    say_as: str = ""
    ipa: str = ""
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Pronunciation:
        return cls(
            word=str(data.get("word", "")).strip(),
            say_as=str(data.get("say_as", "") or "").strip(),
            ipa=str(data.get("ipa", "") or "").strip().strip("/"),
            note=str(data.get("note", "") or "").strip(),
        )

    def to_dict(self) -> dict:
        out = {"word": self.word}
        if self.say_as:
            out["say_as"] = self.say_as
        if self.ipa:
            out["ipa"] = self.ipa
        if self.note:
            out["note"] = self.note
        return out


def _pause_seconds(match: re.Match) -> float:
    value = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    return value / 1000 if unit == "ms" else value


def parse(text: str) -> list[Segment]:
    """Split tts_text into plain text, phoneme overrides and pauses."""
    segments: list[Segment] = []
    position = 0
    for match in MARKUP_RE.finditer(text):
        _add_text(segments, text[position : match.start()])
        pause = PAUSE_RE.fullmatch(match.group(0))
        if pause:
            seconds = _pause_seconds(pause)
            if seconds > MAX_PAUSE_SECONDS:
                raise MarkupError(
                    f"{match.group(0)} is longer than {MAX_PAUSE_SECONDS:g} s; "
                    "hold the shot in the edit instead"
                )
            segments.append(Pause(seconds))
        else:
            override = OVERRIDE_RE.fullmatch(match.group(0))
            phonemes = normalize_ipa(override.group(2))
            if not phonemes:
                raise MarkupError(f"{match.group(0)} has no phonemes between the slashes")
            segments.append(Phonemes(phonemes, override.group(1)))
        position = match.end()
    _add_text(segments, text[position:])
    return segments


def _add_text(segments: list[Segment], text: str) -> None:
    if not text:
        return
    if "[" in text or "]" in text:
        bracket = text.find("[") if "[" in text else text.find("]")
        snippet = text[max(0, bracket - 15) : bracket + 25].strip()
        raise MarkupError(
            f"Unrecognised markup near '{snippet}'. Use [pause:0.4] or [word](/phonemes/)"
        )
    segments.append(Text(text))


def plain_text(text: str) -> str:
    """What the line says, with markup removed: used for counting words."""
    out = []
    for segment in parse(text):
        if isinstance(segment, Text):
            out.append(segment.text)
        elif isinstance(segment, Phonemes):
            out.append(segment.word)
        else:
            out.append(" ")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def free_text(text: str) -> str:
    """Only the parts of the line the phonemizer will guess at."""
    return " ".join(s.text for s in parse(text) if isinstance(s, Text))


def total_pause(text: str) -> float:
    return sum(s.seconds for s in parse(text) if isinstance(s, Pause))


# --- respellings and hand-written phonemes ----------------------------------------


def is_respelling(token: str) -> bool:
    """True for tokens like pah-NEN-kah: hyphenated, one syllable in caps."""
    parts = token.split("-")
    if len(parts) < 2 or not all(p.isalpha() for p in parts):
        return False
    upper = [p for p in parts if p.isupper() and len(p) >= 2]
    lower = [p for p in parts if p.islower()]
    if not upper or not lower or len(upper) + len(lower) != len(parts):
        return False
    return not any(p in ACRONYMS for p in upper)


# Keyboard stand-ins people type for IPA symbols Kokoro knows
_IPA_FIXES = str.maketrans({"g": "ɡ", ":": "ː", "'": "ˈ", "’": "ˈ", "ˑ": "ː"})


def normalize_ipa(ipa: str) -> str:
    """Tidy hand-typed phonemes: g->ɡ, :->ː, '->ˈ, no slashes or brackets."""
    return ipa.strip().strip("/[]").translate(_IPA_FIXES)


def possessive_suffix(ipa: str) -> str:
    """The 's sound after a name: Panenka's -> z, Hoeneß's -> ɪz, Kopf's -> s."""
    core = ipa.rstrip("ːˈˌ ")
    if core.endswith(("s", "z", "ʃ", "ʒ", "tʃ", "dʒ", "ʧ", "ʤ")):
        return "ɪz"
    if core.endswith(("p", "t", "k", "f", "θ")):
        return "s"
    return "z"


# --- applying pronunciations ---------------------------------------------------


def _sub_outside_markup(text: str, pattern: re.Pattern, replace: Callable[[re.Match], str]) -> str:
    """re.sub, but never inside existing [pause:..] or [word](/../) markup."""
    out, position = [], 0
    for match in MARKUP_RE.finditer(text):
        out.append(pattern.sub(replace, text[position : match.start()]))
        out.append(match.group(0))
        position = match.end()
    out.append(pattern.sub(replace, text[position:]))
    return "".join(out)


def _word_pattern(phrase: str) -> re.Pattern:
    words = phrase.split()
    body = r"\s+".join(re.escape(w) for w in words)
    return re.compile(rf"(?<![\w])({body})(['’]s)?(?![\w])", re.IGNORECASE)


def entry_ipa(entry: Pronunciation, lang: str = "en-gb") -> str:
    if entry.ipa:
        return normalize_ipa(entry.ipa)
    if entry.say_as:
        try:
            return respelling_to_ipa(entry.say_as, lang)
        except RespellingError as error:
            raise MarkupError(f"pronunciation for '{entry.word}': {error}") from None
    return ""


def apply_pronunciations(
    text: str,
    entries: Iterable[Pronunciation],
    lang: str = "en-gb",
    detect_respellings: bool = True,
) -> tuple[str, list[str]]:
    """Mark up every listed name (and any inline respelling) with its phonemes.

    Returns the new text and a list of what was applied, for reporting.
    """
    applied: list[str] = []
    usable = [e for e in entries if e.word and (e.ipa or e.say_as)]
    # Longest first, so "Di Stéfano" is matched before "Stéfano"
    usable.sort(key=lambda e: len(e.word), reverse=True)

    for entry in usable:
        ipa = entry_ipa(entry, lang)
        if not ipa:
            continue

        def mark(match: re.Match, ipa=ipa, entry=entry) -> str:
            suffix = possessive_suffix(ipa) if match.group(2) else ""
            applied.append(entry.word)
            return f"[{match.group(0)}](/{ipa}{suffix}/)"

        text = _sub_outside_markup(text, _word_pattern(entry.word), mark)

        # The respelling itself may already be written into tts_text
        if entry.say_as and entry.say_as != entry.word:
            text = _sub_outside_markup(text, _word_pattern(entry.say_as), mark)

    if detect_respellings:

        def mark_respelling(match: re.Match) -> str:
            token = match.group(1)
            if not is_respelling(token):
                return token
            try:
                ipa = respelling_to_ipa(token, lang)
            except RespellingError:
                return token
            applied.append(token)
            return f"[{token}](/{ipa}/)"

        text = _sub_outside_markup(text, RESPELLING_RE, mark_respelling)

    return text, applied
