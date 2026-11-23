# Testing ballvoice

About 20 minutes the first time, most of it the one-time download. Commands are for **Windows PowerShell**; macOS/Linux differences are at the end.

## 1. Install (once)

**uv** installs the right Python by itself, so you don't need to install Python first. Open PowerShell:

```powershell
winget install --id=astral-sh.uv -e
```

(or `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`). **Close and reopen PowerShell** so `uv` is on your PATH, then:

```powershell
cd ~\Documents
git clone https://github.com/Surajp1602/theballremembers-voice.git
cd theballremembers-voice
uv sync --extra dev
uv run ballvoice setup
```

`uv sync` creates `.venv` with Python 3.11–3.13 (it downloads 3.13 if needed; 3.14 isn't supported yet) and installs the exact versions in `uv.lock`. `setup` downloads the voice model (~350 MB) and should end with:

```
  kokoro-v1.0.onnx: downloaded and verified
  voices-v1.0.bin: downloaded and verified
Ready. Try: ballvoice audition
```

## 2. Run the smoke test (2-3 minutes)

```powershell
uv run python examples/smoke_test.py
```

It runs the real commands, renders the feature tour, inspects the audio and prints PASS or FAIL for each step. You want:

```
21/21 checks passed.
```

followed by a list of clips to listen to. If anything fails, the line under it says why; see [Troubleshooting](#troubleshooting).

## 3. Listen (5 minutes)

The smoke test writes to `build\smoke-test\`. Open the folder with `start build\smoke-test`, or play a file with `start build\smoke-test\narration.wav`.

| File | You should hear |
|---|---|
| `narration.wav` | the whole tour, in one natural voice, no clicks or cut-off words |
| `audio\S02.wav` | "nineteen fifty", "five thousand to one" |
| `audio\S03.wav` | kee-lee-AN em-bah-PAY, then em-bah-PAYZ for the possessive |
| `audio\S04.wav` | gwar-dee-OH-la, not GAR-dee-oh-la |
| `audio\S05.wav` | PA-nen-ka, stressed at the start (from `lexicon.json`) |
| `audio\S06.wav` | zhee-ROO, not the letters Z-H-E-E |
| `audio\S07.wav` | a clear held beat before "That silence was exactly…" |
| `audio\S08.wav`, `audio\S09.wav` | the first noticeably slower, the second quicker |
| `narration.wav` around 0:50–0:57 | S10 runs long, and "I was there." starts after it ends, not on top of it |

If a name sounds wrong, that's a pronunciation to tune (step 5), not a bug.

## 4. Pick the channel's voice (10 minutes)

```powershell
uv run ballvoice audition
start auditions
```

This renders the same line in 10 voices and blends. Try your own mix too:

```powershell
uv run ballvoice audition --voices "bm_george:70,bm_lewis:30" "bm_fable:50,am_puck:50"
```

Put the winner in `ballvoice.toml` under `[voice]`.

## 5. Try each feature by hand

**The checker**, on a file that breaks every rule on purpose:

```powershell
uv run ballvoice check examples/broken_on_purpose.json
```

Expect `4 error(s), 7 warning(s)`: an unknown voice (with "Did you mean bm_george?"), a duplicate shot ID, a shot that ends before it starts, a markup typo, digits, an unlisted foreign name, a 23-word sentence, a line that won't fit its shot, a silent shot, a long hook and a low word count. Then confirm the render refuses:

```powershell
uv run ballvoice render examples/broken_on_purpose.json
```

It prints the same list and `Fix the errors above, then render again.`

**A clean render** of the other sample:

```powershell
uv run ballvoice render examples/panenka_short.json
```

The table should say `ok` for every shot and `every line fits its shot`.

**The cache.** Open `examples/panenka_short.json`, change a word in S06's `tts_text`, save, and render again. Only S06 says a time; the other shots say `unchanged`, and it takes seconds.

**Names:**

```powershell
uv run ballvoice phonemes "Hoeneß" --say-as "HUR-ness" -o test.wav
start test.wav
uv run ballvoice lexicon add "Hoeneß" --say-as "HUR-ness"
uv run ballvoice lexicon list
uv run ballvoice lexicon remove "Hoeneß"
```

**One-off lines:**

```powershell
uv run ballvoice say "Sunday. I was on the spot. [pause:0.5] Here's what really happened." -o line.wav
start line.wav
```

## 6. Run the unit tests

```powershell
uv run pytest
```

Expect `80 passed` (the end-to-end render test runs because the models are downloaded).

## 7. Test with a real package

Run the master prompt (PACKAGE mode), save its **whole reply** as `productions\my-first.md`, then:

```powershell
uv run ballvoice check productions\my-first.md
uv run ballvoice render productions\my-first.md
```

Paste any warnings back to the LLM and ask for a corrected PRODUCTION_JSON, or fix them by hand.

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv` is not recognised | Close and reopen PowerShell after installing uv. |
| `uv sync` says no Python satisfies `>=3.11, <3.14` | `uv python install 3.13`, then `uv sync --extra dev` again. |
| `Model files missing … Run: ballvoice setup` | `uv run ballvoice setup` from the repo folder. |
| `setup` fails with a checksum error | Network hiccup; the bad file was deleted, so run `setup` again. |
| `Failed to load espeak shared library` | Reinstall: `uv sync --reinstall --extra dev`. Antivirus can quarantine the bundled espeak DLL; allow it for the `.venv` folder. |
| Rendering is slow | Normal on older CPUs: about real time (a 1-minute Short ≈ 1 minute). Re-renders use the cache. |
| A name is read as letters | Add it to `pronunciations` or the lexicon with a `say_as` respelling. |
| `ballvoice: Voice 'x' is not in the voices file` | `uv run ballvoice voices` shows the exact names. |
| IPA prints as `?` in the console | Only the display; the audio is fine. Use Windows Terminal for full Unicode. |

## macOS / Linux

Install uv with `curl -LsSf https://astral.sh/uv/install.sh | sh`, use `open` (macOS) or `xdg-open` (Linux) instead of `start`, and `/` instead of `\` in paths. Everything else is the same.
