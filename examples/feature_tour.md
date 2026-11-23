# Feature tour (test package)

This file is shaped like a reply from the master prompt: Markdown first, then
the PRODUCTION_JSON block. `ballvoice` reads the JSON straight out of it.
Each shot tests one feature, and the ball says which one, so you can hear
whether it worked. Use it to test the tool, not as a video.

## What each shot tests

| Shot | Feature |
|---|---|
| S01 | the voice blend itself |
| S02 | numbers spelled out in tts_text |
| S03 | `say_as` respellings from the pronunciations list, including a possessive |
| S04 | hand-typed IPA (`gwa:di'ola`), cleaned up to Kokoro symbols |
| S05 | a name from the channel lexicon (`lexicon.json`) |
| S06 | a respelling written straight into the line |
| S07 | an exact `[pause:0.8]` |
| S08 | `tts_speed` 0.85 (slower) |
| S09 | `tts_speed` 1.15 (faster) |
| S10 | a line that is too long for its shot, **on purpose** |
| S11 | a short line that gets pushed back by S10 |
| S12 | a silent end card (no narration) |

## Part B

PRODUCTION_JSON

```json
{
  "video_id": "tbr-feature-tour",
  "channel": "The Ball Remembers",
  "format": "SHORT",
  "pillar": "How Football Works",
  "instagram_highlight": "Explained",
  "era": "PRESENT",
  "title": "Feature tour",
  "hook": {
    "spoken": "Testing, testing. I'm the ball, and I remember everything.",
    "on_screen": "TESTING TESTING",
    "gold_word": "TESTING",
    "type": "The ball's confession"
  },
  "tts": { "engine": "kokoro", "voice": "", "words_per_minute": 150 },
  "pronunciations": [
    { "word": "Kylian", "say_as": "kee-lee-AN" },
    { "word": "Mbappé", "say_as": "em-bah-PAY" },
    { "word": "Guardiola", "ipa": "gwa:di'ola" }
  ],
  "shots": [
    { "id": "S01", "start": 0.0, "end": 4.5, "method": "BALL NARRATOR",
      "vo": "Testing, testing. I'm the ball, and I remember everything.",
      "tts_text": "Testing, testing. I'm the ball, and I remember everything." },
    { "id": "S02", "start": 4.5, "end": 11.0, "method": "MOTION GRAPHIC",
      "vo": "1950. 5000-1. Numbers are spelled out, so I say them right.",
      "tts_text": "Nineteen fifty. Five thousand to one. Numbers are spelled out, so I say them right." },
    { "id": "S03", "start": 11.0, "end": 17.5, "method": "STILL+PUSH",
      "vo": "Kylian Mbappé. Mbappé's name comes from a respelling in the pronunciations list.",
      "tts_text": "Kylian Mbappé. Mbappé's name comes from a respelling in the pronunciations list." },
    { "id": "S04", "start": 17.5, "end": 23.5, "method": "STILL+PUSH",
      "vo": "Pep Guardiola. His name uses hand-typed IPA, cleaned up automatically.",
      "tts_text": "Pep Guardiola. His name uses hand-typed IPA, cleaned up automatically." },
    { "id": "S05", "start": 23.5, "end": 29.0, "method": "STILL+PUSH",
      "vo": "Panenka comes from the channel lexicon, so I never have to learn it twice.",
      "tts_text": "Panenka comes from the channel lexicon, so I never have to learn it twice." },
    { "id": "S06", "start": 29.0, "end": 34.0, "method": "STILL+PUSH",
      "vo": "And this one is written straight into my line: Olivier Giroud.",
      "tts_text": "And this one is written straight into my line: Olivier zhee-ROO." },
    { "id": "S07", "start": 34.0, "end": 40.5, "method": "MOTION GRAPHIC",
      "vo": "Watch the timing. That silence was exactly 0.8 seconds.",
      "tts_text": "Watch the timing. [pause:0.8] That silence was exactly point eight seconds." },
    { "id": "S08", "start": 40.5, "end": 45.0, "method": "BALL NARRATOR", "tts_speed": 0.85,
      "vo": "This line is slower, for a big reveal.",
      "tts_text": "This line is slower, for a big reveal." },
    { "id": "S09", "start": 45.0, "end": 50.0, "method": "BALL NARRATOR", "tts_speed": 1.15,
      "vo": "This one runs faster, for when a line has to squeeze into its shot.",
      "tts_text": "This one runs faster, for when a line has to squeeze into its shot." },
    { "id": "S10", "start": 50.0, "end": 52.5, "method": "BALL NARRATOR",
      "vo": "This line is too long for its shot on purpose, so you see the timing warning.",
      "tts_text": "This line is too long for its shot on purpose, so you see the timing warning." },
    { "id": "S11", "start": 52.5, "end": 54.5, "method": "BALL NARRATOR",
      "vo": "I was there.",
      "tts_text": "I was there." },
    { "id": "S12", "start": 54.5, "end": 56.5, "method": "MOTION GRAPHIC",
      "vo": "", "tts_text": "", "on_screen_text": "Follow @theballremembers" }
  ]
}
```
