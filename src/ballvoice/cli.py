"""Command line: ballvoice <command> ...  (ballvoice -h for the list)"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from . import audio as au
from .config import Config, load_config
from .lexicon import load_lexicon, merge, save_lexicon, upsert
from .markup import MarkupError, Pronunciation, apply_pronunciations, entry_ipa, normalize_ipa
from .respell import RespellingError
from .models import ModelsMissing
from .production import ProductionError, load_production, production_voice
from .voices import VoiceError, describe, label, list_voices, parse_voice_spec, slug

DEFAULT_AUDITION_TEXT = (
    "I remember everything. [pause:0.4] Every kick, every chip, every miss... "
    "and one night in Belgrade, when a penalty floated so softly the whole stadium forgot to breathe."
)
DEFAULT_AUDITION_VOICES = [
    "bm_george", "bm_fable", "bm_lewis", "bm_daniel",
    "am_puck", "am_michael", "am_fenrir", "am_onyx",
    "bm_george:60,bm_fable:40", "bm_lewis:50,am_puck:50",
]


class CliError(Exception):
    pass


# --- helpers -----------------------------------------------------------------------


def _config(args) -> Config:
    return load_config(args.config)


def _voice(args, config: Config, production=None) -> str:
    voice = getattr(args, "voice", None) or (production_voice(production) if production else "") or config.voice
    parse_voice_spec(voice)  # fail early on a malformed blend
    return voice


def _apply_overrides(args, config: Config) -> None:
    if getattr(args, "lang", None):
        config.lang = args.lang
    if getattr(args, "speed", None) is not None:
        config.speed = args.speed


def _entries(config: Config, production=None) -> list[Pronunciation]:
    lexicon = load_lexicon(config.lexicon)
    return merge(lexicon, production.pronunciations) if production else lexicon


def _engine(config: Config):
    from .engine import VoiceEngine

    print("Loading Kokoro...", file=sys.stderr)
    return VoiceEngine(config)


def _print_report(report, production) -> None:
    marks = {"error": "ERROR", "warn": "WARN ", "info": "INFO "}
    for issue in sorted(report.issues, key=lambda i: ["error", "warn", "info"].index(i.level)):
        print(f"  {marks[issue.level]} {issue.where:<14} {issue.message}")
    if report.issues:
        print()
    try:
        voice = describe(report.voice)
    except VoiceError:
        voice = report.voice or "-"
    print(
        f"  {report.total_words} spoken words, ~{report.estimate:.1f}s of narration "
        f"(video runs {production.runtime:.1f}s). Voice: {voice}"
    )
    print(f"  {len(report.errors)} error(s), {len(report.warnings)} warning(s)")


# --- commands ----------------------------------------------------------------------


def cmd_setup(args) -> int:
    from .models import setup

    config = _config(args)
    print(f"Downloading Kokoro model files to {config.models_dir}")
    setup(config.models_dir, force=args.force)
    print("Ready. Try: ballvoice audition")
    return 0


def cmd_voices(args) -> int:
    config = _config(args)
    from .models import require

    require(config.models_dir)
    names = list_voices(config.voices_path)
    groups: dict[str, list[str]] = {}
    for name in names:
        groups.setdefault(label(name), []).append(name)
    for group, members in groups.items():
        print(f"{group:<22} {', '.join(members)}")
    print(f"\nDefault voice: {describe(config.voice)}")
    print("Blend voices with weights, e.g. --voice \"bm_george:60,bm_fable:40\"")
    return 0


def cmd_say(args) -> int:
    config = _config(args)
    _apply_overrides(args, config)
    voice = _voice(args, config)
    text, applied = apply_pronunciations(args.text, _entries(config), config.lang)
    engine = _engine(config)
    clip = engine.synth(text, voice)
    out = Path(args.output)
    au.write_wav(out, clip * au.peak_gain([clip], config.peak_dbfs))
    if applied:
        print(f"Pronunciations used: {', '.join(sorted(set(applied)))}")
    print(f"Wrote {out} ({au.seconds(clip):.2f}s, {describe(voice)})")
    return 0


def cmd_audition(args) -> int:
    config = _config(args)
    _apply_overrides(args, config)
    voices = args.voices or DEFAULT_AUDITION_VOICES
    for voice in voices:
        parse_voice_spec(voice)
    text, _ = apply_pronunciations(args.text, _entries(config), config.lang)
    engine = _engine(config)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = {}
    for voice in voices:
        started = time.time()
        clips[voice] = engine.synth(text, voice)
        print(f"  {describe(voice):<32} {au.seconds(clips[voice]):5.2f}s  ({time.time() - started:.1f}s to render)")
    gain = au.peak_gain(list(clips.values()), config.peak_dbfs)
    for voice, clip in clips.items():
        au.write_wav(out_dir / f"{slug(voice)}.wav", clip * gain)
    print(f"\nWrote {len(clips)} clips to {out_dir}. Listen, pick one, then set it in ballvoice.toml:")
    print('  [voice]\n  voice = "bm_lewis"')
    return 0


def cmd_phonemes(args) -> int:
    config = _config(args)
    _apply_overrides(args, config)
    from .engine import phonemize, unknown_symbols

    print(f"espeak guess:   {phonemize(args.text, config.lang)}")
    entry = None
    if args.say_as or args.ipa:
        entry = Pronunciation(word=args.text, say_as=args.say_as or "", ipa=args.ipa or "")
        ipa = entry_ipa(entry, config.lang)
        print(f"your version:   {ipa}")
        bad = unknown_symbols(ipa.replace(" ", ""))
        if bad:
            print(f"  note: Kokoro can't say {' '.join(sorted(bad))}; those symbols will be dropped")
    if args.output:
        entries = _entries(config)
        if entry:
            entries = merge(entries, [entry])
        text, _ = apply_pronunciations(args.text, entries, config.lang)
        engine = _engine(config)
        voice = _voice(args, config)
        clip = engine.synth(text, voice)
        au.write_wav(Path(args.output), clip * au.peak_gain([clip], config.peak_dbfs))
        print(f"Wrote {args.output}")
    if entry:
        flag = f'--ipa "{normalize_ipa(entry.ipa)}"' if entry.ipa else f'--say-as "{entry.say_as}"'
        print(f'\nHappy with it? Save it for every video:\n  ballvoice lexicon add "{args.text}" {flag}')
    return 0


def cmd_lexicon(args) -> int:
    config = _config(args)
    entries = load_lexicon(config.lexicon)

    if args.action == "list":
        if not entries:
            print(f"The lexicon at {config.lexicon} is empty.")
        for entry in sorted(entries, key=lambda e: e.word.lower()):
            how = f"/{entry.ipa}/" if entry.ipa else entry.say_as
            note = f"  ({entry.note})" if entry.note else ""
            print(f"  {entry.word:<24} {how}{note}")
        return 0

    if args.action == "add":
        if not args.word or not (args.ipa or args.say_as):
            raise CliError("Usage: ballvoice lexicon add WORD (--ipa IPA | --say-as RESPELLING)")
        new = Pronunciation(word=args.word, say_as=args.say_as or "", ipa=normalize_ipa(args.ipa or ""), note=args.note or "")
        entries, replaced = upsert(entries, new)
        save_lexicon(config.lexicon, entries)
        print(f"{'Updated' if replaced else 'Added'} '{args.word}' in {config.lexicon}")
        return 0

    if args.action == "remove":
        kept = [e for e in entries if e.word.lower() != (args.word or "").lower()]
        if len(kept) == len(entries):
            raise CliError(f"'{args.word}' is not in the lexicon")
        save_lexicon(config.lexicon, kept)
        print(f"Removed '{args.word}'")
        return 0

    if args.action == "import":
        production = load_production(args.word)
        added = 0
        for entry in production.pronunciations:
            if entry.word and (entry.ipa or entry.say_as):
                entries, _ = upsert(entries, entry)
                added += 1
        save_lexicon(config.lexicon, entries)
        print(f"Imported {added} pronunciation(s) from {args.word} into {config.lexicon}")
        return 0
    raise CliError(f"Unknown lexicon action {args.action}")


def _lint(args, config, production):
    from .lint import lint

    voice_names = None
    if config.voices_path.exists():
        voice_names = list_voices(config.voices_path)
    return lint(production, config, load_lexicon(config.lexicon), getattr(args, "voice", None), voice_names)


def cmd_check(args) -> int:
    config = _config(args)
    _apply_overrides(args, config)
    production = load_production(args.production)
    narrated = sum(1 for s in production.shots if s.speaks)
    print(f"Checking {args.production}  ({production.format or 'format?'}, {len(production.shots)} shots, {narrated} narrated)\n")
    report = _lint(args, config, production)
    _print_report(report, production)
    return 1 if report.errors else 0


def cmd_render(args) -> int:
    from .render import render

    config = _config(args)
    _apply_overrides(args, config)
    production = load_production(args.production)
    report = _lint(args, config, production)
    if report.errors or report.warnings:
        _print_report(report, production)
        print()
    if report.errors:
        print("Fix the errors above, then render again.")
        return 1
    if args.strict and report.warnings:
        print("--strict: fix the warnings above, then render again.")
        return 1

    voice = _voice(args, config, production)
    out_dir = Path(args.output) if args.output else config.out_dir / production.name
    print(f"Rendering {production.name} with {describe(voice)} at speed {config.speed:g} -> {out_dir}")
    started = time.time()
    manifest = render(
        production, config, voice, _entries(config, production), out_dir,
        speed=config.speed, force=args.force,
    )

    print(f"\n  {'shot':<6}{'window':>9}{'voice':>8}{'at':>8}  fit")
    for shot in manifest["shots"]:
        status = "ok" if shot["fits"] else (
            f"runs {shot['overflow']:.2f}s long" if shot["overflow"] else f"starts {shot['drift']:.2f}s late"
        )
        print(f"  {shot['id']:<6}{shot['window']:>8.2f}s{shot['duration']:>7.2f}s{shot['placed_at']:>7.2f}s  {status}")
    print(
        f"\nDone in {time.time() - started:.0f}s. Narration {manifest['runtime']:.1f}s, "
        f"{'every line fits its shot' if manifest['all_fit'] else 'some lines overrun: trim the text, raise tts_speed, or lengthen the shot'}."
    )
    print(f"  {out_dir / 'narration.wav'}\n  {out_dir / 'voice_manifest.json'}\n  {out_dir / 'audio'}/")

    measured = manifest.get("measured_wpm")
    if measured and abs(measured - config.words_per_minute) / config.words_per_minute > 0.08:
        print(
            f"\nThis voice speaks at about {measured} words a minute. Set words_per_minute = {measured} "
            "under [script] in ballvoice.toml so `check` estimates match real renders."
        )
    return 0


# --- parser ------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="path to ballvoice.toml (default: ./ballvoice.toml if present)")

    voice_opts = argparse.ArgumentParser(add_help=False)
    voice_opts.add_argument("--voice", help='voice or blend, e.g. "bm_george:60,bm_fable:40"')
    voice_opts.add_argument("--speed", type=float, help="0.5-2.0, default from config")
    voice_opts.add_argument("--lang", help="en-gb or en-us, default from config")

    parser = argparse.ArgumentParser(
        prog="ballvoice",
        description="Narration for The Ball Remembers, from PRODUCTION_JSON to timed voice clips.",
    )
    parser.add_argument("--version", action="version", version=f"ballvoice {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    p = sub.add_parser("setup", parents=[common], help="download the Kokoro model files (~350 MB)")
    p.add_argument("--force", action="store_true", help="download again even if present")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("voices", parents=[common], help="list the available voices")
    p.set_defaults(func=cmd_voices)

    p = sub.add_parser("audition", parents=[common, voice_opts], help="render one line in several voices to compare")
    p.add_argument("--voices", nargs="+", help="voices or blends to try (default: a British/American shortlist)")
    p.add_argument("--text", default=DEFAULT_AUDITION_TEXT, help="line to read")
    p.add_argument("-o", "--output", default="auditions", help="folder for the clips (default: auditions)")
    p.set_defaults(func=cmd_audition)

    p = sub.add_parser("say", parents=[common, voice_opts], help="speak one line to a WAV file")
    p.add_argument("text", help="text to speak; [pause:0.4] and [word](/ipa/) work here too")
    p.add_argument("-o", "--output", default="line.wav")
    p.set_defaults(func=cmd_say)

    p = sub.add_parser("phonemes", parents=[common, voice_opts], help="see and test how a name is pronounced")
    p.add_argument("text", help="word or name")
    p.add_argument("--say-as", help="respelling to try, e.g. pah-NEN-kah")
    p.add_argument("--ipa", help="phonemes to try, e.g. pˈanɛŋka")
    p.add_argument("-o", "--output", help="also render it to this WAV file")
    p.set_defaults(func=cmd_phonemes)

    p = sub.add_parser("lexicon", parents=[common], help="the channel's saved pronunciations")
    p.add_argument("action", choices=["list", "add", "remove", "import"])
    p.add_argument("word", nargs="?", help="word for add/remove, or a production file for import")
    p.add_argument("--ipa")
    p.add_argument("--say-as")
    p.add_argument("--note")
    p.set_defaults(func=cmd_lexicon)

    p = sub.add_parser("check", parents=[common, voice_opts], help="check a production's narration without rendering")
    p.add_argument("production", help="PRODUCTION_JSON file, or the whole package saved as a file")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("render", parents=[common, voice_opts], help="render every narrated shot, plus narration.wav and a manifest")
    p.add_argument("production", help="PRODUCTION_JSON file, or the whole package saved as a file")
    p.add_argument("-o", "--output", help="output folder (default: build/<video_id>)")
    p.add_argument("--force", action="store_true", help="re-render every shot, ignoring the cache")
    p.add_argument("--strict", action="store_true", help="stop on warnings too")
    p.set_defaults(func=cmd_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (CliError, ModelsMissing, ProductionError, MarkupError, VoiceError, RuntimeError,
            RespellingError, FileNotFoundError, ValueError) as error:
        print(f"ballvoice: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
