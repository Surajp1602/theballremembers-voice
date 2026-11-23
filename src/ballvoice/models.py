"""Downloading the Kokoro model files.

These are the kokoro-onnx v1.0 files (the same ones nazdridoy/kokoro-tts
uses), checked against their SHA-256 after download.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

FILES = {
    "kokoro-v1.0.onnx": (
        "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
        325_532_387,
    ),
    "voices-v1.0.bin": (
        "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
        28_214_398,
    ),
}


class ModelsMissing(FileNotFoundError):
    pass


def missing(models_dir: Path) -> list[str]:
    return [name for name in FILES if not (models_dir / name).exists()]


def require(models_dir: Path) -> None:
    gone = missing(models_dir)
    if gone:
        raise ModelsMissing(
            f"Model files missing from {models_dir}: {', '.join(gone)}. "
            "Run: ballvoice setup"
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, target: Path, size: int) -> None:
    partial = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "ballvoice"})
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as out:
        total = int(response.headers.get("Content-Length") or size)
        done, shown = 0, -1
        while True:
            block = response.read(1 << 20)
            if not block:
                break
            out.write(block)
            done += len(block)
            percent = int(done * 100 / total) if total else 0
            if percent != shown and percent % 5 == 0:
                shown = percent
                print(f"\r  {target.name}: {percent:3d}% of {total / 1e6:.0f} MB",
                      end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    shutil.move(str(partial), str(target))


def setup(models_dir: Path, force: bool = False) -> None:
    if models_dir.exists() and not models_dir.is_dir():
        raise RuntimeError(
            f"{models_dir} is a file, not a folder. Delete it (or rename it) and run ballvoice setup again."
        )
    models_dir.mkdir(parents=True, exist_ok=True)
    for name, (expected, size) in FILES.items():
        target = models_dir / name
        if target.exists() and not force:
            if target.stat().st_size == size:
                print(f"  {name}: already present")
                continue
            print(f"  {name}: wrong size, downloading again")
        _download(f"{RELEASE}/{name}", target, size)
        actual = sha256(target)
        if actual != expected:
            target.unlink()
            raise RuntimeError(
                f"{name} failed its checksum (got {actual[:12]}…). "
                "The download was removed; run ballvoice setup again."
            )
        print(f"  {name}: downloaded and verified")
