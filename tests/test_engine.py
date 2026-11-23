"""Phonemizer tests (espeak-ng ships with kokoro-onnx), plus a full render when
the model files are present. Point BALLVOICE_MODELS at them, or put them in
./models, to run the integration test."""

import json
import os
import shutil
from pathlib import Path

import pytest

from ballvoice.config import load_config
from ballvoice.engine import phonemize, to_phoneme_groups, unknown_symbols

ROOT = Path(__file__).parent.parent
MODELS = Path(os.environ.get("BALLVOICE_MODELS", ROOT / "models"))
HAVE_MODELS = (MODELS / "kokoro-v1.0.onnx").exists() and (MODELS / "voices-v1.0.bin").exists()


def test_phonemize_british():
    assert phonemize("Sunday.", "en-gb") == "sˈʌndeɪ."


def test_pauses_split_the_line_into_groups():
    groups = to_phoneme_groups("Nothing here [pause:0.3] then a [Panenka](/pˈanɛŋka/).", "en-gb")
    assert groups[1] == pytest.approx(0.3)
    assert isinstance(groups[0], str) and isinstance(groups[2], str)
    assert "pˈanɛŋka." in groups[2]


def test_punctuation_only_groups_are_dropped():
    assert to_phoneme_groups("[pause:0.2] . [pause:0.2]", "en-gb") == [0.2, 0.2]


def test_unknown_symbols():
    assert unknown_symbols("pˈanɛŋka") == set()
    assert unknown_symbols("g") == {"g"}  # plain g isn't in the vocabulary; IPA ɡ is


@pytest.mark.skipif(not HAVE_MODELS, reason="Kokoro model files not downloaded")
def test_render_sample_end_to_end(tmp_path):
    from ballvoice.lexicon import load_lexicon, merge
    from ballvoice.production import load_production
    from ballvoice.render import render

    config = load_config(ROOT / "ballvoice.toml")
    config.models_dir = MODELS
    production = load_production(ROOT / "examples" / "panenka_short.json")
    entries = merge(load_lexicon(ROOT / "lexicon.json"), production.pronunciations)
    out = tmp_path / "out"

    manifest = render(production, config, config.voice, entries, out, progress=lambda *_: None)
    assert manifest["all_fit"]
    assert [s["id"] for s in manifest["shots"]] == [f"S0{i}" for i in range(1, 9)]
    assert (out / "narration.wav").exists()
    assert all((out / s["file"]).exists() for s in manifest["shots"])
    assert 120 <= manifest["measured_wpm"] <= 190
    assert json.loads((out / "voice_manifest.json").read_text(encoding="utf-8"))["runtime"] == pytest.approx(48.4)

    # Second run reuses every clip
    again = render(production, config, config.voice, entries, out, progress=lambda *_: None)
    assert all(s["cached"] for s in again["shots"])
    shutil.rmtree(out)
