import json
from pathlib import Path

import pytest

from ballvoice.production import ProductionError, extract_json, load_production, production_voice

SAMPLE = Path(__file__).parent.parent / "examples" / "panenka_short.json"


def test_loads_the_sample():
    production = load_production(SAMPLE)
    assert production.video_id == "tbr-sample-panenka"
    assert production.format == "SHORT"
    assert len(production.shots) == 9
    assert [s.id for s in production.shots if not s.speaks] == ["S09"]
    assert production.runtime == pytest.approx(48.4)
    assert production.name == "tbr-sample-panenka"


def test_extracts_json_from_a_whole_package(tmp_path):
    body = {"video_id": "x", "shots": [{"id": "S01", "start": 0, "end": 2, "tts_text": "Hi."}]}
    package = (
        "## Angle\nSome markdown with {braces} in it.\n\n"
        "## Part B\nPRODUCTION_JSON\n```json\n" + json.dumps(body, indent=2) + "\n```\n"
    )
    assert extract_json(package) == body
    path = tmp_path / "package.md"
    path.write_text(package, encoding="utf-8")
    assert load_production(path).shots[0].tts_text == "Hi."


def test_missing_production_json_is_an_error():
    with pytest.raises(ProductionError):
        extract_json("no json here {not: valid}")


def test_placeholder_voice_is_ignored(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"tts": {"voice": "[KOKORO VOICE ID]"}, "shots": []}), encoding="utf-8")
    assert production_voice(load_production(path)) == ""
    path.write_text(json.dumps({"tts": {"voice": "bm_lewis"}, "shots": []}), encoding="utf-8")
    assert production_voice(load_production(path)) == "bm_lewis"
