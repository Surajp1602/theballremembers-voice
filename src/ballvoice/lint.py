"""Checks a production against the voice rules in the master prompt.

Errors stop a render. Warnings are worth fixing before you publish. Info
lines are things to listen for.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .config import Config
from .markup import (
    MarkupError,
    Pronunciation,
    apply_pronunciations,
    free_text,
    normalize_ipa,
    plain_text,
    total_pause,
)
from .production import Production, production_voice
from .voices import VoiceError, parse_voice_spec

WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")
# Capitalised words that are not names
COMMON_CAPS = {
    "i", "i'm", "i've", "i'd", "i'll", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday", "january", "february", "march", "april", "may",
    "june", "july", "august", "september", "october", "november", "december",
    "english", "european", "world", "cup", "league", "champions", "premier", "final",
}
WORD_RANGES = {"SHORT": (110, 150), "LONG": (1200, 1800)}
FIT_TOLERANCE = 0.3


@dataclass
class Issue:
    level: str  # "error" | "warn" | "info"
    where: str
    message: str


@dataclass
class ShotStats:
    id: str
    window: float | None
    words: int
    estimate: float


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)
    shots: list[ShotStats] = field(default_factory=list)
    total_words: int = 0
    estimate: float = 0.0
    voice: str = ""

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warn"]

    def add(self, level: str, where: str, message: str) -> None:
        self.issues.append(Issue(level, where, message))


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def _has_foreign_letters(word: str) -> bool:
    return any(ord(ch) > 127 and unicodedata.category(ch).startswith("L") for ch in word)


def lint(
    production: Production,
    config: Config,
    lexicon: list[Pronunciation] | None = None,
    voice_override: str | None = None,
    voice_names: list[str] | None = None,
) -> Report:
    report = Report()
    entries = (lexicon or []) + production.pronunciations
    wpm = int(production.tts.get("words_per_minute") or config.words_per_minute)

    # --- production level ------------------------------------------------------
    engine = str(production.tts.get("engine") or "").lower()
    if engine and engine != "kokoro":
        report.add("warn", "tts", f"engine is '{engine}', but this tool renders with Kokoro")

    voice = voice_override or production_voice(production) or config.voice
    report.voice = voice
    try:
        parse_voice_spec(voice)
        if voice_names is not None:
            from .voices import check_names

            check_names(voice, voice_names)
    except VoiceError as error:
        report.add("error", "voice", str(error))

    if not production.shots:
        report.add("error", "shots", "no shots in the production")

    for entry in production.pronunciations:
        if not entry.word:
            report.add("warn", "pronunciations", "an entry has no word")
        elif not (entry.ipa or entry.say_as):
            report.add("warn", "pronunciations", f"'{entry.word}' has neither say_as nor ipa")
        if entry.ipa:
            try:
                from .engine import unknown_symbols

                bad = unknown_symbols(normalize_ipa(entry.ipa).replace(" ", ""))
            except Exception:  # phonemizer unavailable: skip this check
                bad = set()
            if bad:
                report.add(
                    "warn", "pronunciations",
                    f"'{entry.word}' ipa has symbols Kokoro can't say, they'll be dropped: {' '.join(sorted(bad))}",
                )

    hook = str(production.hook.get("spoken") or "")
    if hook and count_words(hook) > config.max_hook_words:
        report.add(
            "warn", "hook",
            f"spoken hook has {count_words(hook)} words (limit {config.max_hook_words})",
        )

    # --- shots -----------------------------------------------------------------
    seen: set[str] = set()
    previous_end: float | None = None
    used_words: set[str] = set()
    names: dict[str, set[str]] = {}

    for index, shot in enumerate(production.shots):
        where = shot.id or f"shot #{index + 1}"
        if not shot.id:
            report.add("error", where, "shot has no id")
        elif shot.id in seen:
            report.add("error", where, f"duplicate shot id {shot.id}")
        seen.add(shot.id)

        if shot.start is None or shot.end is None:
            report.add("error", where, "start and end must be numbers (seconds)")
        elif shot.end <= shot.start:
            report.add("error", where, f"end ({shot.end}) is not after start ({shot.start})")
        else:
            if previous_end is not None and shot.start < previous_end - 0.01:
                report.add("warn", where, f"starts at {shot.start}s, before the previous shot ends ({previous_end}s)")
            previous_end = shot.end

        if shot.speed is not None and not 0.5 <= shot.speed <= 2.0:
            report.add("error", where, f"tts_speed {shot.speed} is outside 0.5-2.0")

        if not shot.speaks:
            if shot.vo.strip():
                report.add("warn", where, "has a vo line but no tts_text, so it will be silent")
            continue

        try:
            marked, applied = apply_pronunciations(shot.tts_text, entries, config.lang)
            spoken = plain_text(marked)
            guessed = free_text(marked)
            pause = total_pause(marked)
        except MarkupError as error:
            report.add("error", where, str(error))
            continue

        used_words.update(w.lower() for w in applied)
        for token in applied:
            if "-" in token and not any(token.lower() == e.word.lower() for e in entries):
                report.add("info", where, f"reading '{token}' as a respelling")

        digits = re.findall(r"\d[\d,.:]*", guessed)
        if digits:
            report.add(
                "warn", where,
                f"digits in tts_text ({', '.join(digits)}): spell them the way they're said",
            )

        for sentence in SENTENCE_RE.split(spoken):
            length = count_words(sentence)
            if length > config.max_sentence_words:
                preview = sentence if len(sentence) < 70 else sentence[:67] + "..."
                report.add(
                    "warn", where,
                    f"sentence has {length} words (limit {config.max_sentence_words}): \"{preview}\"",
                )

        for sentence in SENTENCE_RE.split(guessed):
            words = WORD_RE.findall(sentence)
            for position, word in enumerate(words):
                key = word.lower()
                if _has_foreign_letters(word):
                    report.add(
                        "warn", where,
                        f"'{word}' isn't plain English spelling; add it to pronunciations",
                    )
                elif position > 0 and word[0].isupper() and key not in COMMON_CAPS:
                    names.setdefault(word, set()).add(where)

        words = count_words(spoken)
        estimate = words / wpm * 60 + pause
        report.total_words += words
        report.estimate += estimate
        report.shots.append(ShotStats(where, shot.window, words, estimate))

        if shot.window is not None and shot.window > 0 and estimate > shot.window + FIT_TOLERANCE:
            report.add(
                "warn", where,
                f"~{estimate:.1f}s of speech at {wpm} wpm for a {shot.window:.1f}s shot",
            )

    if names:
        listed = ", ".join(f"{name} ({', '.join(sorted(places))})" for name, places in sorted(names.items()))
        report.add("info", "names", f"no pronunciation given, listen for: {listed}")

    for entry in production.pronunciations:
        if entry.word and entry.word.lower() not in used_words:
            report.add("info", "pronunciations", f"'{entry.word}' isn't used in any tts_text")

    word_range = WORD_RANGES.get(production.format)
    if word_range and production.shots:
        low, high = word_range
        if not low <= report.total_words <= high:
            report.add(
                "warn", "script",
                f"{report.total_words} spoken words; a {production.format} should have {low}-{high}",
            )
    return report
