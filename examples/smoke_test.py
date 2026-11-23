"""One-command smoke test for ballvoice.

Run from the repo folder after `ballvoice setup`:

    uv run python examples/smoke_test.py          (or: python examples/smoke_test.py)

It drives the real command line, renders examples/feature_tour.md, checks the
audio it produced, and prints PASS or FAIL for each step. At the end it lists
the clips to listen to. Takes 1-3 minutes, mostly rendering.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
TOUR = "examples/feature_tour.md"
BROKEN = "examples/broken_on_purpose.json"
OUT = ROOT / "build" / "smoke-test"

results: list[tuple[str, bool, str]] = []


def ballvoice(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, "-m", "ballvoice", *args],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )


def step(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {name}" + (f"\n        {detail}" if detail and not ok else ""), flush=True)
    return ok


def longest_silence(path: Path) -> float:
    audio, rate = sf.read(str(path), dtype="float32")
    frame = int(rate * 0.01)
    usable = len(audio) // frame * frame
    rms = np.sqrt((audio[:usable].reshape(-1, frame) ** 2).mean(axis=1))
    quiet = rms < rms.max() * 0.03
    best = run = 0
    for q in quiet:
        run = run + 1 if q else 0
        best = max(best, run)
    return best * 0.01


def main() -> int:
    print(f"ballvoice smoke test in {ROOT}\n")

    models = ROOT / "models"
    if not step("model files are downloaded",
                (models / "kokoro-v1.0.onnx").exists() and (models / "voices-v1.0.bin").exists(),
                "run `uv run ballvoice setup` first"):
        return 1

    version = ballvoice("--version")
    step("ballvoice runs", version.returncode == 0, version.stderr.strip())

    # 1. The checker
    check = ballvoice("check", TOUR)
    step("check: feature tour has 0 errors and only the planned warning",
         check.returncode == 0 and "0 error(s), 1 warning(s)" in check.stdout and "S10" in check.stdout,
         check.stdout[-600:] + check.stderr)

    broken = ballvoice("check", BROKEN)
    expected = ["Did you mean bm_george", "duplicate shot id S01", "is not after start",
                "Unrecognised markup", "digits in tts_text (1950)", "'Müller'",
                "sentence has 23 words", "no tts_text", "spoken hook has 16 words"]
    missing = [e for e in expected if e not in broken.stdout]
    step("check: broken file reports every planted problem",
         broken.returncode == 1 and not missing, f"not reported: {missing}")

    refused = ballvoice("render", BROKEN, "-o", str(OUT / "should-not-exist"))
    step("render: refuses a file with errors",
         refused.returncode == 1 and not (OUT / "should-not-exist" / "narration.wav").exists())

    # 2. A full render
    print("\n  rendering the feature tour (about a minute)...", flush=True)
    started = time.time()
    render = ballvoice("render", TOUR, "-o", str(OUT), "--force")
    took = time.time() - started
    if not step(f"render: feature tour finished ({took:.0f}s)", render.returncode == 0,
                render.stdout[-800:] + render.stderr[-800:]):
        return summary()

    manifest = json.loads((OUT / "voice_manifest.json").read_text(encoding="utf-8"))
    shots = {s["id"]: s for s in manifest["shots"]}
    step("manifest: 11 narrated shots, S12 silent",
         sorted(shots) == [f"S{i:02d}" for i in range(1, 12)] and manifest["silent_shots"] == ["S12"])

    files_ok = all((OUT / s["file"]).exists() for s in shots.values()) and (OUT / "narration.wav").exists()
    step("files: a WAV per shot plus narration.wav", files_ok)

    loud = []
    for sid, shot in shots.items():
        audio, rate = sf.read(str(OUT / shot["file"]), dtype="float32")
        loud.append(rate == 24000 and len(audio) / rate > 0.5 and np.abs(audio).max() > 0.1)
    step("audio: every clip is 24 kHz, longer than 0.5s and not silent", all(loud))

    narration, rate = sf.read(str(OUT / "narration.wav"), dtype="float32")
    step("narration.wav covers the whole video",
         abs(len(narration) / rate - manifest["runtime"]) < 0.05 and manifest["runtime"] >= 56.5)

    gap = longest_silence(OUT / shots["S07"]["file"])
    step(f"S07: [pause:0.8] left a gap of {gap:.2f}s", 0.75 <= gap <= 1.3)

    names = [shots["S03"]["text"], shots["S04"]["text"], shots["S05"]["text"], shots["S06"]["text"]]
    step("pronunciations: say_as, possessive, IPA, lexicon and inline respelling all applied",
         "[Mbappé's](/" in names[0] and "ɡwaːdiˈola" in names[1]
         and "[Panenka](/pˈanɛŋka/)" in names[2] and "[zhee-ROO](/" in names[3], "\n".join(names))

    step("tts_speed: S08 slower and S09 faster", shots["S08"]["speed"] == 0.85 and shots["S09"]["speed"] == 1.15)
    slow_rate = len(shots["S08"]["spoken"].split()) / shots["S08"]["duration"]
    fast_rate = len(shots["S09"]["spoken"].split()) / shots["S09"]["duration"]
    step(f"tts_speed: S09 speaks faster than S08 ({fast_rate * 60:.0f} vs {slow_rate * 60:.0f} wpm)",
         fast_rate > slow_rate)

    step("timing: S10 reported as running long", not shots["S10"]["fits"] and shots["S10"]["overflow"] > 1)
    step("timing: S11 pushed back instead of overlapping",
         shots["S11"]["drift"] > 1 and shots["S11"]["placed_at"] >= shots["S10"]["placed_at"] + shots["S10"]["duration"] - 0.2)
    step("timing: the other shots fit",
         all(s["fits"] for sid, s in shots.items() if sid not in ("S10", "S11")))

    # 3. The cache
    again = ballvoice("render", TOUR, "-o", str(OUT))
    step("cache: a second render reuses all 11 clips",
         again.returncode == 0 and again.stdout.count("unchanged") == 11, again.stdout[-400:])

    # 4. Other commands
    say = ballvoice("say", "Panenka's chip. [pause:0.3] I remember everything.", "-o", str(OUT / "say.wav"))
    step("say: writes a WAV", say.returncode == 0 and (OUT / "say.wav").exists(), say.stderr)

    phon = ballvoice("phonemes", "Guardiola", "--ipa", "gwa:di'ola")
    step("phonemes: cleans up hand-typed IPA", phon.returncode == 0 and "ɡwaːdiˈola" in phon.stdout, phon.stdout)

    voices = ballvoice("voices")
    step("voices: lists the British male voices", "bm_george" in voices.stdout and "bm_fable" in voices.stdout)

    return summary()


def summary() -> int:
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("Failed: " + "; ".join(failed))
        return 1

    print(f"\nNow listen. The clips are in {OUT}")
    listen = [
        ("narration.wav", "the whole tour, one line after another"),
        ("audio/S02.wav", "\"nineteen fifty\" and \"five thousand to one\", said naturally"),
        ("audio/S03.wav", "kee-lee-AN em-bah-PAY, then em-bah-PAYZ (the possessive)"),
        ("audio/S04.wav", "gwar-dee-OH-la, not GAR-dee-oh-la"),
        ("audio/S05.wav", "PA-nen-ka with the stress at the start"),
        ("audio/S06.wav", "zhee-ROO, not the letters Z-H-E-E"),
        ("audio/S07.wav", "a clear held beat before \"That silence\""),
        ("audio/S08.wav + S09.wav", "the first noticeably slower, the second quicker"),
    ]
    for file, what in listen:
        print(f"  {file:<26} {what}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
