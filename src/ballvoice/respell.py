"""Respellings to phonemes, using Wikipedia's pronunciation-respelling key.

A respelling is how the master prompt writes a name for the narrator:
hyphenated syllables with the stressed one in capitals.

    pah-NEN-kah    ->  pɑːnˈɛnkɑː
    MY-er          ->  mˈaɪə
    dee STEF-ah-noh ->  diː stˈɛfɑːnəʊ

The rules are fixed and predictable, so a respelling always sounds the same.
Vowels follow the key: a=æ (cat; "a" in British English), ah=ɑː, ay=eɪ, e/eh=ɛ, ee=iː, i/ih=ɪ,
eye/igh=aɪ, o=ɒ, oh=əʊ, oo=uː, uu=ʊ, ow=aʊ, oy=ɔɪ, u/uh=ʌ, ur/er=ɜː,
aw=ɔː, ar=ɑː, or=ɔː, air=ɛə, ear/eer=ɪə, oor=ʊə, ew=juː. In an unstressed
syllable "uh", "er" and a lone "a" become a schwa (ə).
Consonants: ch=tʃ, sh=ʃ, zh=ʒ, th=θ, dh=ð, ng=ŋ, nk=ŋk, kh=x, j=dʒ, g=ɡ,
y=j before a vowel (otherwise the "eye" sound), r=ɹ, c/q=k, x=ks.
"""

from __future__ import annotations

STRESS = "ˈ"

_VOWELS_COMMON = {
    "eye": "aɪ", "igh": "aɪ", "ew": "juː",
    "ah": "ɑː", "aw": "ɔː", "ay": "eɪ", "ee": "iː", "eh": "ɛ", "ih": "ɪ",
    "oo": "uː", "uu": "ʊ", "ow": "aʊ", "oy": "ɔɪ", "uh": "ʌ",
    "a": "æ", "e": "ɛ", "i": "ɪ", "u": "ʌ",
}
_VOWELS = {
    "en-gb": {
        **_VOWELS_COMMON,
        "air": "ɛə", "ear": "ɪə", "eer": "ɪə", "oor": "ʊə", "our": "aʊə",
        "ar": "ɑː", "or": "ɔː", "ur": "ɜː", "er": "ɜː", "oh": "əʊ", "o": "ɒ",
        "a": "a",  # British "cat", written as espeak-ng writes it
    },
    "en-us": {
        **_VOWELS_COMMON,
        "air": "ɛɹ", "ear": "ɪɹ", "eer": "ɪɹ", "oor": "ʊɹ", "our": "aʊɚ",
        "ar": "ɑːɹ", "or": "ɔːɹ", "ur": "ɜːɹ", "er": "ɜːɹ", "oh": "oʊ", "o": "ɑː",
    },
}
_WEAK = {"en-gb": "ə", "en-us": "ə"}
_WEAK_ER = {"en-gb": "ə", "en-us": "ɚ"}

_CONSONANTS = {
    "tch": "tʃ", "ch": "tʃ", "sh": "ʃ", "zh": "ʒ", "th": "θ", "dh": "ð",
    "ng": "ŋ", "nk": "ŋk", "kh": "x", "ph": "f", "wh": "w", "ck": "k",
    "b": "b", "c": "k", "d": "d", "f": "f", "g": "ɡ", "h": "h", "j": "dʒ",
    "k": "k", "l": "l", "m": "m", "n": "n", "p": "p", "q": "k", "r": "ɹ",
    "s": "s", "t": "t", "v": "v", "w": "w", "x": "ks", "z": "z",
}


class RespellingError(ValueError):
    pass


def _lang(lang: str) -> str:
    return "en-us" if lang.lower().startswith("en-us") else "en-gb"


def _syllable(text: str, stressed: bool, lang: str) -> str:
    """Phonemes for one syllable, with a stress mark before its vowel if stressed."""
    vowels = _VOWELS[lang]
    if not stressed:
        if text == "a" or text == "uh":
            return _WEAK[lang]
    out: list[str] = []
    vowel_seen = False
    i = 0
    while i < len(text):
        rest = text[i:]
        ch = text[i]

        # y: a consonant before a vowel, otherwise the "eye" vowel
        if ch == "y":
            nxt = text[i + 1 : i + 2]
            if nxt and nxt in "aeiou":
                out.append("j")
                i += 1
                continue
            sound, size = "aɪ", 1
        else:
            match = next((v for v in sorted(vowels, key=len, reverse=True) if rest.startswith(v)), None)
            # "er" and "uh" that close an unstressed syllable are schwas
            if match in ("er", "uh") and not stressed:
                sound = _WEAK_ER[lang] if match == "er" else _WEAK[lang]
                size = len(match)
            elif match:
                sound, size = vowels[match], len(match)
            else:
                sound = None

        if sound is not None:
            if stressed and not vowel_seen:
                out.append(STRESS)
            out.append(sound)
            vowel_seen = True
            i += size
            continue

        match = next((c for c in sorted(_CONSONANTS, key=len, reverse=True) if rest.startswith(c)), None)
        if match is None:
            raise RespellingError(f"can't read '{ch}' in respelling syllable '{text}'")
        sound = _CONSONANTS[match]
        # Doubled letters are one sound: "ness" ends in one s
        if not (out and out[-1] == sound):
            out.append(sound)
        i += len(match)

    if stressed and not vowel_seen:
        out.insert(0, STRESS)
    return "".join(out)


def respelling_to_ipa(respelling: str, lang: str = "en-gb") -> str:
    """Convert a respelling such as 'pah-NEN-kah' to Kokoro phonemes."""
    lang = _lang(lang)
    words = [w for w in respelling.replace("’", "'").split() if w.strip("-")]
    if not words:
        raise RespellingError("empty respelling")

    split = [[s for s in word.strip("-'").split("-") if s] for word in words]
    any_caps = any(s.isupper() and len(s) > 1 for syllables in split for s in syllables)

    out = []
    for syllables in split:
        if any_caps:
            stressed = {i for i, s in enumerate(syllables) if s.isupper() and len(s) > 1}
        else:
            stressed = {0}
        word = []
        for index, syllable in enumerate(syllables):
            letters = syllable.lower()
            if not letters.isalpha() or not letters.isascii():
                raise RespellingError(
                    f"respelling syllables use plain letters a-z, got '{syllable}'"
                )
            word.append(_syllable(letters, index in stressed, lang))
        out.append("".join(word))
    return " ".join(out)
