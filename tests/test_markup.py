import pytest

from ballvoice.markup import (
    MarkupError,
    Pause,
    Phonemes,
    Pronunciation,
    Text,
    apply_pronunciations,
    free_text,
    is_respelling,
    normalize_ipa,
    parse,
    plain_text,
    possessive_suffix,
    total_pause,
)


def test_parse_pauses_and_overrides():
    segments = parse("I remember. [pause:0.4] [Panenka](/pˈanɛŋka/) chipped me. [pause:250ms]")
    assert segments == [
        Text("I remember. "),
        Pause(0.4),
        Text(" "),
        Phonemes("pˈanɛŋka", "Panenka"),
        Text(" chipped me. "),
        Pause(0.25),
    ]


@pytest.mark.parametrize(
    "text",
    ["a [pause] b", "[pause:abc]", "a [b] c", "missing ] bracket", "[Name](/ /)", "[pause:9]"],
)
def test_bad_markup_is_rejected(text):
    with pytest.raises(MarkupError):
        parse(text)


def test_plain_free_and_pause_helpers():
    text = "Sepp Maier dived. [pause:0.3] [Panenka](/pˈanɛŋka/) didn't blast me."
    assert plain_text(text) == "Sepp Maier dived. Panenka didn't blast me."
    assert "Panenka" not in free_text(text)
    assert total_pause(text) == pytest.approx(0.3)


def test_normalize_ipa_fixes_keyboard_symbols():
    assert normalize_ipa("/gwa:di'ola/") == "ɡwaːdiˈola"


def test_override_ipa_is_normalized_when_parsed():
    assert parse("[Guardiola](/gwa:di'ola/)") == [Phonemes("ɡwaːdiˈola", "Guardiola")]


@pytest.mark.parametrize(
    "ipa, suffix", [("pˈanɛŋka", "z"), ("hˈɜːnɛs", "ɪz"), ("kˈɒpf", "s"), ("bˈɛtʃ", "ɪz")]
)
def test_possessive_suffix(ipa, suffix):
    assert possessive_suffix(ipa) == suffix


ENTRIES = [
    Pronunciation("Panenka", ipa="pˈanɛŋka"),
    Pronunciation("Hoeneß", say_as="HUR-ness"),
    Pronunciation("Di Stéfano", say_as="dee STEF-ah-noh"),
    Pronunciation("Stéfano", ipa="stˈɛfanəʊ"),
]


def test_names_are_marked_up_case_insensitively_with_possessives():
    text, applied = apply_pronunciations("panenka's chip and Hoeneß's miss", ENTRIES)
    assert text == "[panenka's](/pˈanɛŋkaz/) chip and [Hoeneß's](/hˈɜːnɛsɪz/) miss"
    assert applied == ["Panenka", "Hoeneß"]


def test_longest_name_wins():
    text, _ = apply_pronunciations("Alfredo Di Stéfano scored.", ENTRIES)
    assert text == "Alfredo [Di Stéfano](/diː stˈɛfɑːnəʊ/) scored."


def test_existing_markup_is_left_alone():
    original = "[Panenka](/pənˈɛŋkə/) again. [pause:0.2] Panenka."
    text, _ = apply_pronunciations(original, ENTRIES)
    assert text == "[Panenka](/pənˈɛŋkə/) again. [pause:0.2] [Panenka](/pˈanɛŋka/)."


def test_respelling_already_in_tts_text_is_converted():
    entries = [Pronunciation("Panenka", say_as="pah-NEN-kah")]
    text, _ = apply_pronunciations("Then pah-NEN-kah walked up.", entries)
    assert text == "Then [pah-NEN-kah](/pɑːnˈɛnkɑː/) walked up."


def test_unlisted_respellings_are_detected_but_acronyms_are_not():
    text, applied = apply_pronunciations("em-BAH-pay saw a VAR-style call on a TV-friendly night.", [])
    assert text.startswith("[em-BAH-pay](/ɛmbˈɑːpeɪ/) saw a VAR-style call on a TV-friendly night.")
    assert applied == ["em-BAH-pay"]


def test_words_inside_other_words_are_not_matched():
    text, applied = apply_pronunciations("Panenkas and SuperPanenka", ENTRIES)
    assert applied == []
    assert text == "Panenkas and SuperPanenka"


@pytest.mark.parametrize(
    "token, expected",
    [("pah-NEN-kah", True), ("PAH-nen", True), ("well-known", False), ("VAR-check", False),
     ("X-ray", False), ("five-to-three", False)],
)
def test_is_respelling(token, expected):
    assert is_respelling(token) is expected
