import json
from pathlib import Path

from ballvoice.config import Config
from ballvoice.lexicon import load_lexicon
from ballvoice.lint import lint
from ballvoice.production import load_production

ROOT = Path(__file__).parent.parent


def _production(tmp_path, data):
    path = tmp_path / "p.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_production(path)


def _messages(report, level):
    return [f"{i.where}: {i.message}" for i in report.issues if i.level == level]


def test_sample_has_no_errors_or_warnings():
    production = load_production(ROOT / "examples" / "panenka_short.json")
    report = lint(production, Config(), load_lexicon(ROOT / "lexicon.json"))
    assert report.errors == []
    assert report.warnings == []
    assert report.total_words == 110


def test_catches_the_voice_rules(tmp_path):
    production = _production(tmp_path, {
        "format": "SHORT",
        "hook": {"spoken": "one two three four five six seven eight nine ten eleven twelve thirteen"},
        "tts": {"engine": "qwen3"},
        "shots": [
            {"id": "S01", "start": 0, "end": 2, "tts_text": "In 1976 the final went to penalties."},
            {"id": "S02", "start": 2, "end": 4, "tts_text": (
                "This sentence keeps going and going and going well past the eighteen word limit "
                "that the master prompt sets for every line."
            )},
            {"id": "S03", "start": 4, "end": 6, "tts_text": "Then Müller scored."},
            {"id": "S04", "start": 6, "end": 8, "vo": "A line nobody will hear."},
        ],
    })
    report = lint(production, Config())
    warnings = "\n".join(_messages(report, "warn"))
    assert "digits in tts_text (1976)" in warnings
    assert "sentence has 22 words" in warnings
    assert "for a 2.0s shot" in warnings
    assert "'Müller' isn't plain English spelling" in warnings
    assert "vo line but no tts_text" in warnings
    assert "spoken hook has 13 words" in warnings
    assert "engine is 'qwen3'" in warnings
    assert "a SHORT should have 110-150" in warnings
    assert report.errors == []


def test_structural_errors(tmp_path):
    production = _production(tmp_path, {"shots": [
        {"id": "S01", "start": 0, "end": 2, "tts_text": "Fine."},
        {"id": "S01", "start": 3, "end": 2, "tts_text": "Backwards [bad markup] here."},
        {"start": "x", "end": 5, "tts_text": "No id.", "tts_speed": 3},
    ]})
    errors = "\n".join(_messages(lint(production, Config()), "error"))
    assert "duplicate shot id S01" in errors
    assert "end (2.0) is not after start (3.0)" in errors
    assert "Unrecognised markup" in errors
    assert "shot has no id" in errors
    assert "start and end must be numbers" in errors
    assert "tts_speed 3.0 is outside" in errors


def test_tts_speed_changes_the_estimate(tmp_path):
    line = "one two three four five six seven eight nine ten"  # 4.0s at 150 wpm
    production = _production(tmp_path, {"shots": [
        {"id": "S01", "start": 0, "end": 3, "tts_text": line, "tts_speed": 1.5},
        {"id": "S02", "start": 3, "end": 7, "tts_text": line, "tts_speed": 0.8},
    ]})
    report = lint(production, Config())
    assert [round(s.estimate, 2) for s in report.shots] == [2.67, 5.0]
    assert [i.where for i in report.warnings if "for a" in i.message] == ["S02"]


def test_bad_voice_is_an_error(tmp_path):
    production = _production(tmp_path, {"shots": [{"id": "S01", "start": 0, "end": 3, "tts_text": "Hi."}]})
    report = lint(production, Config(), voice_override="bm_georg", voice_names=["bm_george"])
    assert any("Did you mean bm_george" in i.message for i in report.errors)


def test_pronunciations_cover_names(tmp_path):
    production = _production(tmp_path, {
        "pronunciations": [{"word": "Müller", "say_as": "MUE-ler"}, {"word": "Unused", "say_as": "UN-yoozd"}],
        "shots": [{"id": "S01", "start": 0, "end": 3, "tts_text": "Then Müller scored."}],
    })
    report = lint(production, Config())
    assert not any("Müller" in i.message for i in report.warnings)
    assert any("'Unused' isn't used" in i.message for i in report.issues if i.level == "info")
