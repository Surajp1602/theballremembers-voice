import numpy as np
import pytest

from ballvoice.voices import VoiceError, blend_style, check_names, describe, parse_voice_spec, slug


def test_single_voice():
    assert parse_voice_spec("bm_george") == [("bm_george", 1.0)]


def test_weighted_blend_is_normalised():
    assert parse_voice_spec("bm_george:60, bm_fable:40") == [("bm_george", 0.6), ("bm_fable", 0.4)]
    assert parse_voice_spec("bm_george:3,bm_fable:2") == [("bm_george", 0.6), ("bm_fable", 0.4)]


def test_unweighted_list_is_an_equal_blend():
    assert parse_voice_spec("am_adam,af_sarah") == [("am_adam", 0.5), ("af_sarah", 0.5)]


@pytest.mark.parametrize("spec", ["", "George", "bm_george:abc", "bm_george:0", "bm_george:-1"])
def test_bad_specs(spec):
    with pytest.raises(VoiceError):
        parse_voice_spec(spec)


def test_describe_and_slug():
    assert describe("bm_george:60,bm_fable:40") == "bm_george 60% + bm_fable 40%"
    assert slug("bm_george:60,bm_fable:40") == "bm_george-60_bm_fable-40"
    assert slug("bm_lewis") == "bm_lewis"


def test_blend_style_mixes_by_weight():
    styles = {"bm_george": np.ones((2, 1, 3), np.float32), "bm_fable": np.zeros((2, 1, 3), np.float32)}
    mixed = blend_style("bm_george:75,bm_fable:25", styles)
    assert mixed.dtype == np.float32
    assert np.allclose(mixed, 0.75)


def test_unknown_voice_suggests_close_names():
    with pytest.raises(VoiceError, match="Did you mean bm_george"):
        check_names("bm_georg", ["bm_george", "bm_fable"])
