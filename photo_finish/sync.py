"""Align camera scratch audio to a continuous lavalier master by signal similarity.

The audio is never transcribed or edited to find a sync point.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import numpy as np

from .project import Project, has_audio


SAMPLE_RATE = 8000
HOP_SECONDS = 0.08


def decode_audio(path: Path, *, seconds: float | None = None, rate: int = SAMPLE_RATE) -> np.ndarray:
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
           "-i", str(path)]
    if seconds is not None:
        cmd += ["-t", str(seconds)]
    cmd += ["-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "pipe:1"]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Install FFmpeg and ensure ffmpeg is on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Cannot decode sound from {path}: {exc.stderr.decode(errors='replace')}") from exc
    return np.frombuffer(result.stdout, dtype="<f4").copy()


def energy_envelope(samples: np.ndarray, *, rate: int = SAMPLE_RATE) -> np.ndarray:
    """Slow amplitude modulation follows the same speech across microphones."""
    hop = max(1, round(rate * HOP_SECONDS))
    count = len(samples) // hop
    if not count:
        raise ValueError("Audio is too short to synchronize")
    frames = samples[:count * hop].reshape(count, hop).astype(np.float64)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    # Compress microphone-level differences; emphasize phrase onsets.
    compressed = np.log1p(40 * rms)
    smooth = np.convolve(compressed, np.ones(5) / 5, mode="same")
    return np.diff(smooth, prepend=smooth[0])


def estimate_offset(master: np.ndarray, camera: np.ndarray, *, max_lag_seconds: float = 60) -> tuple[float, float]:
    """Return camera start relative to master, and correlation quality.

    Positive offset means the camera recording begins later than microphone
    audio; frame at global time t is camera-local time t - offset.
    """
    if max_lag_seconds < 0:
        raise ValueError("max_lag_seconds cannot be negative")
    max_bins = round(max_lag_seconds / HOP_SECONDS)
    best_score, best_lag = -2.0, 0
    for lag in range(-max_bins, max_bins + 1):
        if lag >= 0:
            a, b = master[lag:], camera
        else:
            a, b = master, camera[-lag:]
        size = min(len(a), len(b))
        if size < round(8 / HOP_SECONDS):
            continue
        a, b = a[:size], b[:size]
        a, b = a - a.mean(), b - b.mean()
        denominator = np.linalg.norm(a) * np.linalg.norm(b)
        if denominator < 1e-10:
            continue
        score = float(np.dot(a, b) / denominator)
        if score > best_score:
            best_score, best_lag = score, lag
    if best_score < 0.25:
        raise ValueError(
            f"Audio alignment is uncertain (similarity {best_score:.2f}). "
            "Set an explicit offset_seconds for this camera."
        )
    return round(best_lag * HOP_SECONDS, 3), round(best_score, 3)


def synchronize(project: Project, *, max_lag_seconds: float = 60) -> dict[str, float]:
    """Respect explicit offsets; infer others from scratch audio against lav."""
    offsets = {camera.name: camera.offset_seconds for camera in project.cameras}
    automatic = [c for c in project.cameras if c.offset_seconds is None]
    if automatic:
        master = energy_envelope(decode_audio(project.audio, seconds=150))
        for camera in automatic:
            if not has_audio(camera.path):
                raise ValueError(
                    f"{camera.name}: no scratch audio for synchronization; "
                    "supply offset_seconds in the manifest"
                )
            envelope = energy_envelope(decode_audio(camera.path, seconds=150))
            offset, _quality = estimate_offset(
                master, envelope, max_lag_seconds=max_lag_seconds
            )
            offsets[camera.name] = offset
    return {name: float(offset) for name, offset in offsets.items()}
