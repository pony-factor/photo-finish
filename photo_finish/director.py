"""Plan cuts with local audio prosody and visual framing, without rewriting speech."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Callable

from .analysis import AudioMoment, VisualMoment, VisualSampler, analyze_voice, choose_main
from .project import Project, Source, duration
from .sync import decode_audio


@dataclass(frozen=True)
class Shot:
    start: float
    end: float
    source: str
    kind: str
    gentle_pan: bool = False


@dataclass
class EditPlan:
    duration: float
    audio: str
    main_camera: str
    offsets: dict[str, float]
    roles: dict[str, str]
    shots: list[Shot]

    def save(self, filename: str | Path) -> None:
        payload = {
            "duration": self.duration,
            "audio": self.audio,
            "main_camera": self.main_camera,
            "offsets": self.offsets,
            "roles": self.roles,
            "shots": [asdict(shot) for shot in self.shots],
        }
        Path(filename).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def camera_roles(project: Project, main: str,
                 snapshots: dict[str, list[VisualMoment]]) -> dict[str, str]:
    """Classify at the beginning; per-camera role overrides take precedence."""
    roles: dict[str, str] = {}
    for camera in project.cameras:
        if camera.role != "auto":
            roles[camera.name] = camera.role
        elif camera.name == main:
            roles[camera.name] = "main"
        else:
            frames = snapshots.get(camera.name, [])
            fraction = sum(f.face_fraction for f in frames) / len(frames) if frames else 0
            if fraction >= .11:
                roles[camera.name] = "closeup"
            elif frames and sum(f.face_visible for f in frames) / len(frames) > .5 and fraction < .017:
                roles[camera.name] = "wide"
            else:
                roles[camera.name] = "side"
    return roles


def _source_available(source: Source, offsets: dict[str, float],
                      lengths: dict[str, float], start: float, end: float) -> bool:
    offset = offsets[source.name]
    return start >= offset - .0001 and end <= offset + lengths[source.name] + .0001


def validate_shots(shots: list[Shot], end: float) -> None:
    """Guard against missing, overlapping or deleted content."""
    if not shots or abs(shots[0].start) > .01 or abs(shots[-1].end - end) > .01:
        raise ValueError("Edit would omit part of the microphone recording")
    for first, second in zip(shots, shots[1:]):
        if abs(first.end - second.start) > .01:
            raise ValueError("Edit has a gap or overlap")
    if any(s.end <= s.start for s in shots):
        raise ValueError("Edit contains a nonpositive shot")


def make_plan(project: Project, offsets: dict[str, float], *,
              step: float = 2.0, min_shot: float = 4.0, side_max: float = 12.0,
              on_progress: Callable[[str], None] | None = None) -> EditPlan:
    """Use the main angle for emphasis/movement and side angles for steady delivery.

    Preserve every millisecond of the separate microphone recording. Visual-only
    cuts do not affect speech, silence, fillers, or delivery.
    """
    if step <= 0 or min_shot <= 0 or side_max < min_shot:
        raise ValueError("Invalid cut timing parameters")
    end = duration(project.audio)
    lengths = {camera.name: duration(camera.path) for camera in project.cameras}
    if project.slides:
        lengths[project.slides.name] = duration(project.slides.path)
    moments = analyze_voice(decode_audio(project.audio), step=step)
    with VisualSampler() as sampler:
        if on_progress:
            on_progress("Classifying cameras from their opening frames")
        initial: dict[str, list[VisualMoment]] = {}
        for camera in project.cameras:
            frames = [sampler.snapshot(camera.path, t - offsets[camera.name])
                      for t in (2.0, 4.0, 6.0)]
            initial[camera.name] = [frame for frame in frames if frame is not None]
        main = choose_main(project.cameras, initial)
        roles = camera_roles(project, main, initial)
        sources = {c.name: c for c in project.cameras}
        if project.slides:
            sources[project.slides.name] = project.slides
        time_offsets = {**offsets}
        if project.slides:
            time_offsets[project.slides.name] = project.slides.offset_seconds or 0.0

        shots: list[Shot] = []
        active: str | None = None
        start = 0.0
        steady_for = 0.0
        slide_until = -1.0
        last_seen: dict[str, float] = {}

        def append(until: float) -> None:
            if active is not None and until > start:
                kind = "slides" if project.slides and active == project.slides.name else roles[active]
                shots.append(Shot(round(start, 3), round(until, 3), active,
                                  kind, kind in {"side", "closeup"}))

        if on_progress:
            on_progress("Planning cuts from prosody, gestures and visual composition")
        for moment in moments:
            t = moment.time
            limit = min(end, t + step)
            if t >= end:
                break
            available = [cam for cam in project.cameras
                         if _source_available(cam, time_offsets, lengths, t, limit)]
            if not available:
                raise ValueError(
                    f"No camera footage covers {t:.1f}–{limit:.1f}s of lavalier audio. "
                    "Add a covering camera or correct synchronization offsets."
                )
            # Look only at relevant, sparse frames; none of the speech is decoded as text.
            views = {cam.name: sampler.snapshot(cam.path, t - offsets[cam.name] + .2)
                     for cam in available}
            main_choice = main if main in views else max(
                available, key=lambda c: views[c.name].quality if views[c.name] else 0
            ).name
            motion = views[main_choice].movement if views[main_choice] else 0.0
            expressive = moment.emphasis >= .48 or motion >= .64
            steady_for = 0 if expressive or moment.pause else steady_for + step

            candidates = [c for c in available if c.name != main_choice]
            def desirability(c: Source) -> float:
                shot = views[c.name]
                quality = shot.quality if shot else 0.0
                role_bonus = {"side": .22, "closeup": .12, "wide": .04, "main": 0}.get(roles[c.name], 0)
                recency = .24 if t - last_seen.get(c.name, -1000) < 18 else 0.0
                return quality + role_bonus - recency

            other = max(candidates, key=desirability).name if candidates else main_choice
            slides_active = False
            if project.slides and _source_available(project.slides, time_offsets, lengths, t, limit):
                if t >= step and sampler.slide_changed(project.slides, t, t - step):
                    slide_until = t + 8.0
                slides_active = t < slide_until and not expressive

            target = main_choice
            if slides_active:
                target = project.slides.name
            elif active and active != main_choice and active != (project.slides.name if project.slides else None):
                if expressive or t - start >= side_max:
                    target = main_choice
                else:
                    target = active
            elif steady_for >= 8.0 and candidates and not expressive:
                target = other

            if active is None:
                active, start = target, t
            elif target != active:
                if t - start < min_shot and _source_available(sources[active], time_offsets, lengths, t, limit):
                    continue
                append(t)
                last_seen[active] = t
                start, active = t, target
            if not _source_available(sources[active], time_offsets, lengths, t, limit):
                append(t)
                last_seen[active] = t
                start, active = t, main_choice

        append(end)
    validate_shots(shots, end)
    return EditPlan(end, str(project.audio), main, time_offsets, roles, shots)
