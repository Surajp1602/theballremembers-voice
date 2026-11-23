# The Ball Remembers: voice

`ballvoice` turns a PRODUCTION_JSON from the master prompt into the ball's narration: one clip per shot, a full narration track on the video's timeline, and a manifest Remotion can read. It runs on your own computer, free, with the **Kokoro-82M** voice model (Apache-2.0, fine for a monetized channel).

It uses the same engine and model files as [nazdridoy/kokoro-tts](https://github.com/nazdridoy/kokoro-tts) (kokoro-onnx + the v1.0 Kokoro files) and adds what the channel's pipeline needs:

- **One clip per shot**, named by shot ID (`S01.wav`, `S02.wav` …), plus `narration.wav` with every clip placed at its shot's start time.
- **Pronunciations that stick.** Names get the right sound from a respelling (`pah-NEN-kah`) or IPA, per video or saved once in the channel lexicon.
- **A signature voice.** Weighted blends such as `bm_george:60,bm_fable:40`, and an audition command to compare them.
- **Timing checks.** It warns when a line won't fit its shot before you render, measures the real length after, and pushes later lines back instead of overlapping them.
- **The master prompt's voice rules**, checked automatically: 18-word sentences, numbers spelled out, a 12-word hook, word counts for SHORT and LONG, names without a pronunciation.
- **Fast re-renders.** Only shots whose text, voice or pronunciation changed are synthesized again.

---

## Install

You need Python 3.11, 3.12 or 3.13 and about 400 MB of disk. It works on Windows, macOS and Linux, and espeak-ng comes bundled, so there's nothing else to install.

```bash
git clone https://github.com/Surajp1602/theballremembers-voice.git
cd theballremembers-voice

# with uv (recommended: it fetches a compatible Python and the locked versions)
uv sync
uv run ballvoice setup     # downloads the Kokoro model files (~350 MB) into models/

# or with plain pip and Python 3.11-3.13
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e .
ballvoice setup
```

With uv, prefix commands with `uv run` (e.g. `uv run ballvoice render ...`), or activate `.venv` and drop the prefix. Step-by-step Windows instructions are in [TESTING.md](TESTING.md).

## Quick start

```bash
ballvoice audition                              # one line in 10 voices/blends -> auditions/
ballvoice check  examples/panenka_short.json    # rules check, no audio
ballvoice render examples/panenka_short.json    # -> build/tbr-sample-panenka/
```

Open `build/tbr-sample-panenka/narration.wav` and listen. That sample is only for testing the tool; its script hasn't been source-checked.

**Testing it properly:** follow [TESTING.md](TESTING.md). `examples/smoke_test.py` runs every feature against `examples/feature_tour.md` (one shot per feature) and `examples/broken_on_purpose.json` (one shot per rule), and prints PASS/FAIL.

## Making a video's narration

1. **Get the package.** Run the master prompt in PACKAGE or NEWS mode. Save the whole reply as a file, e.g. `productions/2026-12-01-panenka.md`. `ballvoice` finds the PRODUCTION_JSON inside it, or you can save just the JSON.
2. **Check it.** `ballvoice check productions/2026-12-01-panenka.md`. Fix any warnings by hand, or paste them back to the LLM and ask for a corrected PRODUCTION_JSON.
3. **Render it.** `ballvoice render productions/2026-12-01-panenka.md`, then listen to `narration.wav`. The table shows any line that runs past its shot.
4. **Fix a name** that sounds wrong:
   ```bash
   ballvoice phonemes "Hoeneß" --say-as "HUR-ness" -o test.wav     # try it
   ballvoice lexicon add "Hoeneß" --say-as "HUR-ness"              # keep it for every video
   ```
5. **Render again.** Only the changed shots are re-synthesized (seconds, not minutes).
6. **Assemble in Remotion** with `voice_manifest.json` (see [Using it in Remotion](#using-it-in-remotion)).

## Writing `tts_text`

Plain English sentences, plus three optional bits of markup:

| You write | What happens |
|---|---|
| `[pause:0.4]` or `[pause:400ms]` | an exact hold of 0.4 s (max 5 s). Use it before a reveal. |
| `[Panenka](/pˈanɛŋka/)` | this word is said with these phonemes (Kokoro's own syntax) |
| `pah-NEN-kah` | a respelling written straight into the text is converted to phonemes |

Punctuation still shapes delivery: `...` gives a held beat, a dash a pivot, a full stop a drop before a reveal.

**Keep real names in `tts_text`** (`Antonín Panenka`, not `AN-toh-neen pah-NEN-kah`) and put the sounds in `pronunciations`. Both styles work, but real names keep the manifest readable and let the lexicon do its job.

## Pronunciations

Every name the narrator might fumble goes in the production's `pronunciations` list:

```json
"pronunciations": [
  { "word": "Hoeneß", "say_as": "HUR-ness" },
  { "word": "Panenka", "ipa": "pˈanɛŋka" }
]
```

- `say_as` is a **respelling**: hyphenated syllables with the stressed one in CAPITALS. It's read with Wikipedia's respelling key: `a` cat · `ah` father · `ay` day · `e`/`eh` bed · `ee` see · `i`/`ih` sit · `eye`/`igh` my · `o` hot · `oh` go · `oo` food · `uu` book · `ow` now · `oy` boy · `u`/`uh` cup · `ur`/`er` her · `aw` law · `ar` car · `or` more · `air` hair · `ear` near · `ch` · `sh` · `zh` (measure) · `th` · `dh` (this) · `ng` · `kh` (loch) · `j`. In an unstressed syllable, `uh`, `er` and a lone `a` become a schwa.
- `ipa` is exact phonemes and wins over `say_as`. Keyboard stand-ins are fixed automatically: `g`→`ɡ`, `:`→`ː`, `'`→`ˈ`.
- Possessives work: `Panenka's` gets the right `z`.
- Matching ignores case and whole words only (`Panenka` won't match `Panenkas`). Longer names match first (`Di Stéfano` before `Stéfano`).

**The channel lexicon** (`lexicon.json`) holds names for every video. A production's own entry wins for that video.

```bash
ballvoice lexicon list
ballvoice lexicon add "Mbappé" --say-as "em-BAH-pay" --note "Kylian"
ballvoice lexicon import productions/2026-12-01-panenka.md   # keep this video's names
ballvoice lexicon remove "Mbappé"
```

## The voice

```bash
ballvoice voices                                          # everything in the voices file
ballvoice audition                                        # a shortlist, as WAVs in auditions/
ballvoice audition --voices bm_george "bm_george:70,bm_lewis:30" --text "I was there."
```

Set the winner in `ballvoice.toml` under `[voice]`. A production can also name a voice in `tts.voice`, and `--voice` on the command line beats both. The channel's voice is `bm_lewis` (British male, chosen for the historical stories). Audition again before changing it, because this voice *is* the channel's voice.

## Output

```
build/<video_id>/
  narration.wav          all clips on the video's timeline (24 kHz mono, 16-bit)
  audio/S01.wav ...      one clip per narrated shot, all at matched loudness
  voice_manifest.json    timings for the edit
  .cache/                raw clips, so unchanged shots aren't re-rendered
```

`voice_manifest.json` (per shot):

| field | meaning |
|---|---|
| `id`, `file` | shot ID and its clip, e.g. `audio/S03.wav` |
| `start`, `end`, `window` | the shot's slot from PRODUCTION_JSON, in seconds |
| `duration` | the clip's real length |
| `placed_at`, `start_frame` | where the clip starts on the timeline (seconds / frames at `fps`) |
| `duration_frames` | clip length in frames |
| `overflow` | seconds the line runs past its shot's end |
| `drift` | seconds the line was pushed back because the previous one ran long |
| `fits` | true when there's no overflow or drift |
| `text`, `spoken` | the marked-up text that was synthesized, and the plain words |

Top level: `runtime`, `runtime_frames`, `fps`, `voice`, `measured_wpm` (how fast this voice really speaks; set `words_per_minute` to it so `check` estimates match), `all_fit`, `silent_shots`.

### Using it in Remotion

Copy the output folder into your Remotion project's `public/voice/<video_id>/`, then either play the single track or place clips per shot:

```tsx
import { Audio, Sequence, staticFile } from "remotion";
import manifest from "../public/voice/tbr-sample-panenka/voice_manifest.json";

const base = `voice/${manifest.video_id}`;

// Option 1: one track
export const Narration = () => <Audio src={staticFile(`${base}/narration.wav`)} />;

// Option 2: a clip per shot, so a shot can be moved without re-rendering
export const NarrationByShot = () => (
  <>
    {manifest.shots.map((s) => (
      <Sequence key={s.id} from={s.start_frame} durationInFrames={s.duration_frames}>
        <Audio src={staticFile(`${base}/${s.file}`)} />
      </Sequence>
    ))}
  </>
);
```

For the audio-reactive ball, drive its bounce from `narration.wav` with `useAudioData` and `visualizeAudio` from `@remotion/media-utils`. Set `fps` in `ballvoice.toml` to match your composition.

## Commands

| command | what it does |
|---|---|
| `ballvoice setup` | download and verify the model files |
| `ballvoice voices` | list voices by accent and gender |
| `ballvoice audition [--voices ...] [--text ...]` | render one line in several voices to compare |
| `ballvoice say "text" -o line.wav` | speak one line (markup and lexicon apply) |
| `ballvoice phonemes NAME [--say-as ...] [--ipa ...] [-o test.wav]` | see espeak's guess, try yours, hear it |
| `ballvoice lexicon list/add/remove/import` | manage the channel's saved names |
| `ballvoice check FILE` | rules check, no audio; exits 1 on errors |
| `ballvoice render FILE [-o DIR] [--force] [--strict]` | render clips, narration and manifest |

`--voice`, `--speed` and `--lang` work on `audition`, `say`, `phonemes`, `check` and `render`. `--config` points at another settings file.

## Settings (`ballvoice.toml`)

All optional; paths are relative to the file.

| section | setting | default |
|---|---|---|
| `[voice]` | `voice`, `lang`, `speed` | `bm_lewis`, `en-gb`, `1.0` |
| `[script]` | `words_per_minute`, `max_sentence_words`, `max_hook_words` | `150`, `18`, `12` |
| `[render]` | `sentence_pause`, `clause_pause`, `tail_ms`, `peak_dbfs`, `fps` | `0.25`, `0.1`, `120`, `-1.0`, `30` |
| `[paths]` | `models_dir`, `lexicon`, `out_dir` | `models`, `lexicon.json`, `build` |

A shot can set `"tts_speed"` (0.5–2.0) to slow a reveal or tighten a line without touching the others.

## Updating the master prompt

The full, current master prompt is in [prompts/MASTER_PROMPT.md](prompts/MASTER_PROMPT.md): paste it into a new chat session to start producing. If you keep your own copy instead, replace its **VOICE PRODUCTION** section with:

```markdown
## VOICE PRODUCTION (free, and licensed for a monetized channel)
- Narration is rendered with ballvoice (Kokoro-82M, Apache-2.0). Voice: bm_lewis. Never use the ElevenLabs free plan (no commercial licence) or F5-TTS / XTTS-v2 (non-commercial model weights).
- Write for TTS: sentences of 18 words or fewer. "..." for a held beat, a dash for a pivot, a full stop before a reveal. For an exact hold write [pause:0.4] (seconds); at most two per Short.
- In tts_text, spell numbers and years the way they should be spoken ("nineteen fifty", "five thousand to one"). On-screen text keeps digits ("1950", "5000-1").
- Keep the real spelling of every name in tts_text. List every non-English name in PRONUNCIATIONS as {"word", "say_as"}: say_as is a respelling with hyphenated syllables and the stressed syllable in CAPITALS, using Wikipedia's respelling key (ah, ay, ee, eye, oh, oo, ow, oy, uh, ur, zh, kh), e.g. {"word": "Panenka", "say_as": "PAH-nen-kah"}. Add "ipa" only when certain of it.
- One tts_text per shot, IDs matching the shot list. A shot may set "tts_speed" (0.9-1.15) to slow a reveal or tighten a line.
- Pace: about 150 spoken words a minute. SHORT 110-150 words; LONG 1,200-1,800 words.
```

In the PRODUCTION_JSON schema, change the pronunciations line to
`"pronunciations": [{"word": "", "say_as": "", "ipa": ""}],` and set `"tts": {"engine": "kokoro", "voice": "bm_lewis", "words_per_minute": 150}`.

## Development

```bash
uv pip install -e ".[dev]"
pytest                      # the full render test runs when models/ is present
```

## Licences and credits

- This project: MIT (see [LICENSE](LICENSE)).
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad: Apache-2.0, commercial use allowed.
- [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) by thewh1teagle: MIT. It also hosts the model files `ballvoice setup` downloads.
- [nazdridoy/kokoro-tts](https://github.com/nazdridoy/kokoro-tts): MIT. This project follows its approach (kokoro-onnx, the v1.0 files, the `voice:weight` blend syntax). No code is copied from it.
- espeak-ng (GPL-3.0) is installed by pip as a separate library through espeakng-loader and used as a phonemizer. It isn't included in this repository.

See [NOTICE.md](NOTICE.md) for details.
