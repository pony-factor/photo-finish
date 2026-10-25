"""Typed project manifests and ffprobe inspection (no transcription)."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess


ROLES = {"auto", "main", "side", "wide", "closeup"}


@dataclass(frozen=True)
class Source:
    name: str
    path: Path
    role: str = "auto"
    offset_seconds: float | None = None


@dataclass(frozen=True)
class Project:
    audio: Path
    cameras: tuple[Source, ...]
    slides: Source | None = None


def _source(item: object, base: Path, index: int, *, slides: bool = False) -> Source:
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        raise ValueError("Each source must be an object containing a path")
    path = (base / item["path"]).resolve()
    if not path.is_file():
        raise ValueError(f"Source does not exist: {path}")
    name = item.get("name", "slides" if slides else f"camera-{index + 1}")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Source name must be a nonempty string")
    role = item.get("role", "wide" if slides else "auto")
    if role not in ({"wide"} if slides else ROLES):
        raise ValueError(f"Unsupported camera role: {role}")
    offset = item.get("offset_seconds", 0.0 if slides else None)
    if offset is not None:
        if isinstance(offset, bool) or not isinstance(offset, (int, float)):
            raise ValueError("offset_seconds must be a number or null")
        offset = float(offset)
    return Source(name, path, role, offset)


def load_project(manifest: str | Path) -> Project:
    manifest = Path(manifest).expanduser().resolve()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Project manifest must be a JSON object")
    audio_path = data.get("audio")
    if not isinstance(audio_path, str):
        raise ValueError("audio must be a path to the separate microphone recording")
    audio = (manifest.parent / audio_path).resolve()
    if not audio.is_file():
        raise ValueError(f"Microphone recording does not exist: {audio}")
    cameras_data = data.get("cameras")
    if not isinstance(cameras_data, list) or not cameras_data:
        raise ValueError("Provide one or more cameras; there is no fixed camera limit")
    cameras = tuple(_source(item, manifest.parent, i) for i, item in enumerate(cameras_data))
    if len({cam.name for cam in cameras}) != len(cameras):
        raise ValueError("Camera names must be unique")
    slides = _source(data["slides"], manifest.parent, 0, slides=True) if data.get("slides") is not None else None
    if slides and slides.name in {camera.name for camera in cameras}:
        raise ValueError("Slides source name must differ from camera names")
    return Project(audio, cameras, slides)


def probe(path: Path) -> dict:
    """Return ffprobe JSON metadata, failing clearly if FFmpeg is absent."""
    try:
        process = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Install FFmpeg and ensure ffprobe is on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Cannot inspect {path}: {exc.stderr.strip()}") from exc
    return json.loads(process.stdout)


def duration(path: Path) -> float:
    info = probe(path)
    value = info.get("format", {}).get("duration")
    if value is None:
        raise ValueError(f"Could not determine recording duration: {path}")
    return float(value)


def has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(path).get("streams", []))
