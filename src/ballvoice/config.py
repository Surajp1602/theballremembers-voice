"""Channel settings, read from ballvoice.toml.

The file is optional. Without one the defaults below are used and every path
is taken relative to the folder you run the command from. With one, paths in
it are relative to the file itself, so the tool works from any folder.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

CONFIG_NAME = "ballvoice.toml"

# Which [section] each setting lives in
SECTIONS: dict[str, tuple[str, ...]] = {
    "voice": ("voice", "lang", "speed"),
    "script": ("words_per_minute", "max_sentence_words", "max_hook_words"),
    "render": ("sentence_pause", "clause_pause", "tail_ms", "peak_dbfs", "fps"),
    "paths": ("models_dir", "lexicon", "out_dir"),
}


@dataclass
class Config:
    # [voice]
    voice: str = "bm_lewis"
    lang: str = "en-gb"
    speed: float = 1.0
    # [script]
    words_per_minute: int = 150
    max_sentence_words: int = 18
    max_hook_words: int = 12
    # [render]
    sentence_pause: float = 0.25
    clause_pause: float = 0.1
    tail_ms: int = 120
    peak_dbfs: float = -1.0
    fps: int = 30
    # [paths]
    models_dir: Path = Path("models")
    lexicon: Path = Path("lexicon.json")
    out_dir: Path = Path("build")

    source: Path | None = None

    @property
    def model_path(self) -> Path:
        return self.models_dir / "kokoro-v1.0.onnx"

    @property
    def voices_path(self) -> Path:
        return self.models_dir / "voices-v1.0.bin"


def _coerce(name: str, value):
    """Convert a TOML value to the type of the matching Config field."""
    kind = {f.name: f.type for f in fields(Config)}[name]
    try:
        if kind == "Path":
            return Path(str(value))
        if kind == "int":
            return int(value)
        if kind == "float":
            return float(value)
        return str(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Setting '{name}' has a bad value {value!r}: {error}") from None


def load_config(path: str | Path | None = None) -> Config:
    """Load settings from `path`, or from ./ballvoice.toml when it exists."""
    if path is None:
        candidate = Path.cwd() / CONFIG_NAME
        path = candidate if candidate.exists() else None

    config = Config()
    base = Path.cwd()

    if path is not None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        base = path.resolve().parent
        config.source = path

        for section, values in data.items():
            if section not in SECTIONS or not isinstance(values, dict):
                raise ValueError(
                    f"Unknown section [{section}] in {path}. "
                    f"Expected one of: {', '.join(SECTIONS)}"
                )
            for key, value in values.items():
                if key not in SECTIONS[section]:
                    raise ValueError(
                        f"Unknown setting '{key}' in [{section}] of {path}. "
                        f"Expected one of: {', '.join(SECTIONS[section])}"
                    )
                setattr(config, key, _coerce(key, value))

    for name in SECTIONS["paths"]:
        value: Path = getattr(config, name)
        if not value.is_absolute():
            setattr(config, name, (base / value).resolve())
    return config
