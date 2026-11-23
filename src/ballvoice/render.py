"""Rendering a production: one clip per shot, a full narration track, a manifest.

Output folder (build/<video_id>/ by default):

    audio/S01.wav ...        one clip per narrated shot, loudness-matched
    narration.wav            every clip placed on the video's timeline
    voice_manifest.json      timings for Remotion (seconds and frames)
    .cache/                  raw clips, so unchanged shots aren't re-rendered
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from . import __version__
from . import audio as au
from .config import Config
from .engine import VoiceEngine
from .markup import Pronunciation, apply_pronunciations, plain_text
from .models import FILES
from .production import Production

FIT_TOLERANCE = 0.05


@dataclass
class Placement:
    id: str
    start: float
    end: float
    duration: float
    placed_at: float
    tail: float = 0.0  # padded silence at the end of the clip

    @property
    def ends_at(self) -> float:
        return self.placed_at + self.duration

    @property
    def drift(self) -> float:
        return self.placed_at - self.start

    @property
    def overflow(self) -> float:
        """Seconds the spoken words run past the shot (padded silence doesn't count)."""
        return max(0.0, self.ends_at - self.tail - self.end)

    @property
    def fits(self) -> bool:
        return self.overflow <= FIT_TOLERANCE and self.drift <= FIT_TOLERANCE


def plan_timeline(items: list[tuple[str, float, float, float]], tail: float = 0.0) -> list[Placement]:
    """Place each clip at its shot's start, or right after the previous clip.

    `items` are (id, start, end, duration). A clip never overlaps the one
    before it: when a line runs long, the next one is pushed back and its
    drift is reported.
    """
    placements, cursor = [], 0.0
    for shot_id, start, end, duration in sorted(items, key=lambda item: item[1]):
        at = max(start, cursor)
        placements.append(Placement(shot_id, start, end, duration, at, min(tail, duration)))
        cursor = at + duration
    return placements


@dataclass
class ShotResult:
    id: str
    file: str
    text: str
    spoken: str
    start: float
    end: float
    window: float
    duration: float
    placed_at: float
    drift: float
    overflow: float
    fits: bool
    start_frame: int
    duration_frames: int
    speed: float
    cached: bool


def _cache_key(text: str, voice: str, speed: float, config: Config) -> str:
    payload = json.dumps(
        [text, voice, speed, config.lang, config.sentence_pause, config.clause_pause,
         FILES["kokoro-v1.0.onnx"][0], __version__],
        ensure_ascii=False,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def render(
    production: Production,
    config: Config,
    voice: str,
    entries: list[Pronunciation],
    out_dir: Path,
    speed: float | None = None,
    force: bool = False,
    engine: VoiceEngine | None = None,
    progress=print,
) -> dict:
    base_speed = speed if speed is not None else config.speed
    cache_dir = out_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    index_path = cache_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    narrated = [s for s in production.shots if s.speaks]
    raw: dict[str, np.ndarray] = {}
    texts: dict[str, str] = {}
    speeds: dict[str, float] = {}
    cached: dict[str, bool] = {}

    for number, shot in enumerate(narrated, 1):
        text, _ = apply_pronunciations(shot.tts_text, entries, config.lang)
        shot_speed = shot.speed if shot.speed is not None else base_speed
        key = _cache_key(text, voice, shot_speed, config)
        clip_path = cache_dir / f"{shot.id}.wav"

        if not force and index.get(shot.id) == key and clip_path.exists():
            raw[shot.id] = au.read_wav(clip_path)
            cached[shot.id] = True
            progress(f"  [{number}/{len(narrated)}] {shot.id}  unchanged")
        else:
            if engine is None:
                progress("  loading Kokoro...")
                engine = VoiceEngine(config)
            raw[shot.id] = engine.synth(text, voice, speed=shot_speed)
            au.write_wav(clip_path, raw[shot.id], subtype="FLOAT")
            index[shot.id] = key
            cached[shot.id] = False
            progress(f"  [{number}/{len(narrated)}] {shot.id}  {au.seconds(raw[shot.id]):.2f}s")
        texts[shot.id] = text
        speeds[shot.id] = shot_speed

    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    # Same gain for every clip keeps the shots matched in loudness
    clips = {sid: au.pad_tail(a, config.tail_ms) for sid, a in raw.items()}
    gain = au.peak_gain(list(clips.values()), config.peak_dbfs)
    clips = {sid: a * gain for sid, a in clips.items()}

    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for stale in audio_dir.glob("*.wav"):
        if stale.stem not in clips:
            stale.unlink()
    for sid, clip in clips.items():
        au.write_wav(audio_dir / f"{sid}.wav", clip)

    by_id = {s.id: s for s in narrated}
    placements = plan_timeline(
        [(sid, by_id[sid].start, by_id[sid].end, au.seconds(c)) for sid, c in clips.items()],
        tail=config.tail_ms / 1000,
    )

    runtime = max([production.runtime] + [p.ends_at for p in placements])
    track = au.silence(runtime)
    for p in placements:
        begin = int(round(p.placed_at * au.SAMPLE_RATE))
        clip = clips[p.id]
        track[begin : begin + len(clip)] += clip[: len(track) - begin]
    au.write_wav(out_dir / "narration.wav", track)

    fps = config.fps
    results = []
    for p in placements:
        shot = by_id[p.id]
        results.append(
            ShotResult(
                id=p.id,
                file=f"audio/{p.id}.wav",
                text=texts[p.id],
                spoken=plain_text(texts[p.id]),
                start=p.start,
                end=p.end,
                window=round(p.end - p.start, 3),
                duration=round(p.duration, 3),
                placed_at=round(p.placed_at, 3),
                drift=round(p.drift, 3),
                overflow=round(p.overflow, 3),
                fits=p.fits,
                start_frame=int(round(p.placed_at * fps)),
                duration_frames=int(math.ceil(p.duration * fps)),
                speed=speeds[p.id],
                cached=cached[p.id],
            )
        )

    # How fast this voice actually speaks, to calibrate `check` estimates
    from .lint import count_words
    from .markup import total_pause

    spoken_words = sum(count_words(plain_text(t)) for t in texts.values())
    speech_seconds = sum(au.seconds(a) for a in raw.values()) - sum(total_pause(t) for t in texts.values())
    measured_wpm = round(spoken_words / speech_seconds * 60) if speech_seconds > 0 else None

    manifest = {
        "video_id": production.video_id,
        "title": production.title,
        "format": production.format,
        "voice": voice,
        "lang": config.lang,
        "speed": base_speed,
        "sample_rate": au.SAMPLE_RATE,
        "fps": fps,
        "narration": "narration.wav",
        "runtime": round(runtime, 3),
        "runtime_frames": int(math.ceil(runtime * fps)),
        "gain_db": round(20 * math.log10(gain), 2) if gain > 0 else None,
        "measured_wpm": measured_wpm,
        "all_fit": all(r.fits for r in results),
        "silent_shots": [s.id for s in production.shots if not s.speaks],
        "shots": [asdict(r) for r in results],
        "generator": f"ballvoice {__version__}",
    }
    (out_dir / "voice_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
