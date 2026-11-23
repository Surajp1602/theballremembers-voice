import pytest

from ballvoice.respell import RespellingError, respelling_to_ipa


@pytest.mark.parametrize(
    "respelling, british, american",
    [
        ("pah-NEN-kah", "pɑːnˈɛnkɑː", "pɑːnˈɛnkɑː"),
        ("MY-er", "mˈaɪə", "mˈaɪɚ"),
        ("HUR-ness", "hˈɜːnɛs", "hˈɜːɹnɛs"),
        ("AN-toh-neen", "ˈantəʊniːn", "ˈæntoʊniːn"),
        ("RON-uh-doh", "ɹˈɒnədəʊ", "ɹˈɑːnədoʊ"),
        ("peh-LAY", "pɛlˈeɪ", "pɛlˈeɪ"),
        ("zhee-ROO", "ʒiːɹˈuː", "ʒiːɹˈuː"),
        ("khah-BEEB", "xɑːbˈiːb", "xɑːbˈiːb"),
        ("KROYF", "kɹˈɔɪf", "kɹˈɔɪf"),
        ("SHEV-chen-koh", "ʃˈɛvtʃɛnkəʊ", "ʃˈɛvtʃɛnkoʊ"),
    ],
)
def test_respellings(respelling, british, american):
    assert respelling_to_ipa(respelling, "en-gb") == british
    assert respelling_to_ipa(respelling, "en-us") == american


def test_unstressed_words_stay_unstressed_when_another_word_has_caps():
    assert respelling_to_ipa("dee STEF-ah-noh") == "diː stˈɛfɑːnəʊ"


def test_no_caps_stresses_first_syllable_of_each_word():
    assert respelling_to_ipa("kroyf") == "kɹˈɔɪf"
    assert respelling_to_ipa("pah-nen-kah") == "pˈɑːnɛnkɑː"


def test_y_is_a_consonant_before_a_vowel_and_eye_otherwise():
    assert respelling_to_ipa("YAY") == "jˈeɪ"
    assert respelling_to_ipa("MY") == "mˈaɪ"


def test_doubled_letters_are_one_sound():
    assert respelling_to_ipa("NESS") == "nˈɛs"


def test_weak_a_and_uh_become_schwa():
    assert respelling_to_ipa("MAR-a-DOH-nuh") == "mˈɑːədˈəʊnə"


@pytest.mark.parametrize("bad", ["", "pah-NÉN-kah", "pah-N3N"])
def test_bad_respellings(bad):
    with pytest.raises(RespellingError):
        respelling_to_ipa(bad)
