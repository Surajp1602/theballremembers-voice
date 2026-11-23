from pathlib import Path

import pytest

from ballvoice.config import Config, load_config
from ballvoice.render import plan_timeline

ROOT = Path(__file__).parent.parent


def test_clips_start_on_their_shot():
    placements = plan_timeline([("S01", 0.0, 4.0, 3.5), ("S02", 4.0, 8.0, 3.0)])
    assert [p.placed_at for p in placements] == [0.0, 4.0]
    assert all(p.fits for p in placements)


def test_a_long_line_pushes_the_next_one_back():
    s1, s2, s3 = plan_timeline([("S01", 0.0, 3.0, 4.0), ("S02", 3.0, 6.0, 2.0), ("S03", 8.0, 10.0, 1.0)])
    assert s1.overflow == pytest.approx(1.0) and not s1.fits
    assert s2.placed_at == pytest.approx(4.0) and s2.drift == pytest.approx(1.0) and not s2.fits
    assert s3.placed_at == pytest.approx(8.0) and s3.fits


def test_padded_silence_does_not_count_as_running_long():
    (placement,) = plan_timeline([("S01", 0.0, 4.0, 4.1)], tail=0.12)
    assert placement.overflow == 0.0 and placement.fits
    (placement,) = plan_timeline([("S01", 0.0, 4.0, 4.3)], tail=0.12)
    assert placement.overflow == pytest.approx(0.18) and not placement.fits


def test_shots_are_placed_in_time_order():
    placements = plan_timeline([("S02", 5.0, 9.0, 1.0), ("S01", 0.0, 5.0, 1.0)])
    assert [p.id for p in placements] == ["S01", "S02"]


def test_repo_config_loads_with_absolute_paths():
    config = load_config(ROOT / "ballvoice.toml")
    assert config.voice == "bm_george:60,bm_fable:40"
    assert config.models_dir == (ROOT / "models").resolve()
    assert config.model_path.name == "kokoro-v1.0.onnx"


def test_defaults_without_a_config_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.source is None
    assert config.lang == "en-gb"
    assert config.out_dir == (tmp_path / "build").resolve()


@pytest.mark.parametrize(
    "toml, message",
    [("[voice]\nvoicee = 'x'\n", "Unknown setting 'voicee'"),
     ("[sound]\nx = 1\n", r"Unknown section \[sound\]"),
     ("[voice]\nspeed = 'fast'\n", "bad value")],
)
def test_config_mistakes_are_explained(tmp_path, toml, message):
    path = tmp_path / "ballvoice.toml"
    path.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_config(path)


def test_config_dataclass_defaults_match_the_master_prompt():
    config = Config()
    assert (config.words_per_minute, config.max_sentence_words, config.max_hook_words) == (150, 18, 12)
