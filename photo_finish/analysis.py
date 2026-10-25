"""Transcript-free prosody and visual-composition measurements.

OpenCV's bundled face detector is a modest local baseline, not a guarantee
of recognizing every profile. Users can override incorrectly inferred roles.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

from .project import Source


@dataclass(frozen=True)
class AudioMoment:
    time: float
    loudness: float
    pitch_hz: float
    emphasis: float
    steady: bool
    pause: bool


def _pitch(samples: np.ndarray, rate: int) -> float:
    """Autocorrelation F0 estimate for voiced sections; zero for unvoiced."""
    if samples.size < 512:
        return 0.0
    frame = samples[:min(samples.size, 2048)].astype(np.float64)
    frame = (frame - frame.mean()) * np.hanning(len(frame))
    if np.sqrt(np.mean(frame * frame)) < .001:
        return 0.0
    nfft = 1 << (len(frame) * 2 - 1).bit_length()
    spectrum = np.fft.rfft(frame, n=nfft)
    correlation = np.fft.irfft(spectrum * np.conj(spectrum), n=nfft)[:len(frame)]
    lo, hi = max(1, round(rate / 350)), min(len(frame), round(rate / 75))
    if hi <= lo or correlation[0] <= 0:
        return 0.0
    lag = int(np.argmax(correlation[lo:hi]) + lo)
    if correlation[lag] / correlation[0] < .27:
        return 0.0
    return float(rate / lag)


def analyze_voice(samples: np.ndarray, *, rate: int = 8000, step: float = 2.0) -> list[AudioMoment]:
    """Score delivery, not words; retains all speech, ums and silences."""
    length = max(1, round(rate * step))
    chunks = [samples[i:i + length] for i in range(0, len(samples), length)]
    chunks = [c for c in chunks if c.size > rate // 4]
    if not chunks:
        raise ValueError("Microphone audio has no usable samples")
    rms = np.array([float(np.sqrt(np.mean(np.square(c.astype(np.float64))))) for c in chunks])
    pitches = np.array([_pitch(c[len(c)//3:], rate) for c in chunks])
    median = max(.00001, float(np.median(rms[rms > .0001]))) if np.any(rms > .0001) else .00001
    moments: list[AudioMoment] = []
    for i, level in enumerate(rms):
        context = rms[max(0, i - 5):min(len(rms), i + 6)]
        local_median = max(median * .3, float(np.median(context)))
        energy = max(0.0, min(1.0, (level / local_median - .7) / 1.2))
        change = 0.0 if i == 0 else min(1.0, abs(level - rms[i-1]) / local_median)
        pitch_change = 0.0
        if i and pitches[i] and pitches[i - 1]:
            pitch_change = min(1.0, abs(pitches[i] - pitches[i - 1]) / 65.0)
        emphasis = min(1.0, .45 * energy + .3 * change + .25 * pitch_change)
        pause = level < max(.003, median * .13)
        moments.append(AudioMoment(i * step, float(level), float(pitches[i]),
                                   float(emphasis), bool(emphasis < .32), bool(pause)))
    return moments


@dataclass(frozen=True)
class VisualMoment:
    face_visible: bool
    face_fraction: float
    center_score: float
    sharpness: float
    movement: float
    brightness: float

    @property
    def quality(self) -> float:
        return (.32 * self.sharpness + .27 * self.center_score
                + .26 * float(self.face_visible) + .15 * self.brightness)


class VisualSampler:
    """Seek sparse frames from local video; close handles after planning."""
    def __init__(self):
        self._captures: dict[Path, cv2.VideoCapture] = {}
        self._face = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if self._face.empty():
            raise RuntimeError("OpenCV's bundled face classifier was not found")

    def close(self) -> None:
        for capture in self._captures.values():
            capture.release()
        self._captures.clear()

    def __enter__(self) -> "VisualSampler":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def frame(self, path: Path, second: float) -> np.ndarray | None:
        if second < 0:
            return None
        if path not in self._captures:
            self._captures[path] = cv2.VideoCapture(str(path))
        capture = self._captures[path]
        if not capture.isOpened():
            return None
        capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
        ok, frame = capture.read()
        if not ok:
            return None
        h, w = frame.shape[:2]
        if max(w, h) > 640:
            scale = 640 / max(w, h)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        return frame

    def snapshot(self, path: Path, second: float) -> VisualMoment | None:
        image = self.frame(path, second)
        if image is None:
            return None
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self._face.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4,
                                            minSize=(22, 22))
        face = max(faces, key=lambda f: f[2] * f[3]) if len(faces) else None
        h, w = gray.shape
        face_fraction = 0.0
        centered = .35
        if face is not None:
            x, y, fw, fh = face
            face_fraction = float(fw * fh / (w * h))
            cx, cy = (x + fw / 2) / w, (y + fh / 2) / h
            centered = max(0.0, 1 - abs(cx - .5) * 1.65 - abs(cy - .45) * .7)
        sharpness = min(1.0, float(cv2.Laplacian(gray, cv2.CV_64F).var()) / 150)
        brightness = min(1.0, float(np.mean(gray)) / 90)
        previous = self.frame(path, max(0, second - .5))
        movement = 0.0
        if previous is not None and previous.shape == image.shape:
            a = cv2.GaussianBlur(cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY), (7, 7), 0)
            b = cv2.GaussianBlur(gray, (7, 7), 0)
            movement = min(1.0, float(np.mean(cv2.absdiff(a, b))) / 18)
        return VisualMoment(face is not None, face_fraction, centered,
                            sharpness, movement, brightness)

    def slide_changed(self, slide: Source, current: float, previous: float) -> bool:
        offset = slide.offset_seconds or 0.0
        a = self.frame(slide.path, previous - offset)
        b = self.frame(slide.path, current - offset)
        if a is None or b is None or a.shape != b.shape:
            return False
        return float(np.mean(cv2.absdiff(a, b))) / 255 > .085


def choose_main(cameras: tuple[Source, ...],
                snapshots: dict[str, list[VisualMoment]]) -> str:
    """Prefer explicit main role, then consistent frontal framing and clarity."""
    explicit = [cam.name for cam in cameras if cam.role == "main"]
    if len(explicit) > 1:
        raise ValueError("Only one camera should be marked as main")
    if explicit:
        return explicit[0]
    def score(cam: Source) -> float:
        frames = snapshots.get(cam.name, [])
        if not frames:
            return -1.0
        return sum((.5 * f.quality + .35 * float(f.face_visible)
                    + .15 * (1 - min(1.0, f.face_fraction * 5)))
                   for f in frames) / len(frames)
    automatic = [cam for cam in cameras if cam.role == "auto"]
    candidates = automatic or list(cameras)
    return max(candidates, key=score).name
