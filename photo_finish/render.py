"""FFmpeg assembly keeps the lavalier soundtrack continuous across all video cuts."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from .director import EditPlan, Shot, validate_shots
from .project import Project, Source, duration


def video_filter(shot: Shot, *, width: int, height: int, fps: int) -> str:
    """Smooth side-angle reframe; stable main; noncropping full-screen slides."""
    if shot.kind == "slides":
        return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1,fps={fps},format=yuv420p")
    if shot.gentle_pan:
        # Spare 8% space for a subtle horizontal digital camera move.
        zoom_width = round(width * 1.08 / 2) * 2
        zoom_height = round(height * 1.08 / 2) * 2
        return (f"scale={zoom_width}:{zoom_height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:(iw-ow)*(0.5+0.13*sin(n/{fps * 5})):(ih-oh)/2,"
                f"setsar=1,fps={fps},format=yuv420p")
    return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p")


def _run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Install FFmpeg and ensure ffmpeg is on PATH") from exc
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.decode("utf-8", errors="replace")[-1800:] if exc.stderr else str(exc)
        raise RuntimeError(f"FFmpeg failed: {msg}") from exc


def render(project: Project, plan: EditPlan, output: str | Path, *,
           width: int = 1920, height: int = 1080, fps: int = 30,
           clean_audio: bool = True) -> Path:
    """Encode selected camera segments, then lay original master audio over once.

    Re-encoding video is necessary for cuts and camera pans; lav audio is *never*
    split at camera boundaries. Optional denoising/normalization cannot remove
    any words or pauses because there is no speech detection or time editing.
    """
    if min(width, height, fps) <= 0 or width % 2 or height % 2:
        raise ValueError("Dimensions must be positive even numbers; fps positive")
    validate_shots(plan.shots, plan.duration)
    dest = Path(output).expanduser().resolve()
    originals = {project.audio.resolve(), *(c.path.resolve() for c in project.cameras)}
    if project.slides:
        originals.add(project.slides.path.resolve())
    if dest in originals:
        raise ValueError("Refusing to overwrite a source recording")
    if dest.exists():
        raise FileExistsError(f"Output already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    sources: dict[str, Source] = {c.name: c for c in project.cameras}
    if project.slides:
        sources[project.slides.name] = project.slides
    with tempfile.TemporaryDirectory(prefix="photo-finish-") as work:
        scratch = Path(work)
        segment_names: list[Path] = []
        for index, shot in enumerate(plan.shots):
            source = sources[shot.source]
            local_time = shot.start - plan.offsets[shot.source]
            if local_time < -0.005:
                raise ValueError(f"Negative source time for {shot.source}")
            segment = scratch / f"segment-{index:05d}.mp4"
            command = [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(max(0.0, local_time)), "-i", str(source.path),
                "-t", str(shot.end - shot.start), "-an",
                "-vf", video_filter(shot, width=width, height=height, fps=fps),
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(fps), str(segment),
            ]
            _run(command)
            segment_names.append(segment)
        concat_list = scratch / "segments.txt"
        # Paths are generated inside our temporary directory; no untrusted inputs.
        concat_list.write_text(
            "".join(f"file '{segment.as_posix()}'\n" for segment in segment_names),
            encoding="utf-8"
        )
        joined = scratch / "video.mp4"
        _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
              "-f", "concat", "-safe", "0", "-i", str(concat_list),
              "-c", "copy", "-an", str(joined)])
        final = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                 "-n", "-i", str(joined), "-i", str(project.audio),
                 "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k"]
        if clean_audio:
            final += ["-af", "highpass=f=80,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"]
        final += ["-t", str(plan.duration), "-movflags", "+faststart", str(dest)]
        _run(final)
    rendered_length = duration(dest)
    if abs(rendered_length - plan.duration) > .25:
        raise RuntimeError(
            f"Rendered media duration {rendered_length:.2f}s differs from "
            f"original microphone audio {plan.duration:.2f}s"
        )
    return dest
