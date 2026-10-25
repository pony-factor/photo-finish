"""Command-line entry point for local transcript-free multicamera editing."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .director import EditPlan, make_plan
from .project import load_project, probe
from .render import render
from .sync import synchronize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="photo-finish",
        description="Auto-direct any number of cameras using prosody and visual composition; no transcription.",
    )
    actions = parser.add_subparsers(dest="action", required=True)
    inspect_cmd = actions.add_parser("inspect", help="Inspect supplied sources and media metadata")
    inspect_cmd.add_argument("project", type=Path)

    plan_cmd = actions.add_parser("plan", help="Analyze cameras and create an editable JSON cut plan")
    plan_cmd.add_argument("project", type=Path)
    plan_cmd.add_argument("-o", "--output", type=Path, default=Path("photo-finish-plan.json"))
    plan_cmd.add_argument("--max-sync-lag", type=float, default=60)

    render_cmd = actions.add_parser("render", help="Build an MP4 without removing or transcribing speech")
    render_cmd.add_argument("project", type=Path)
    render_cmd.add_argument("-o", "--output", type=Path, required=True)
    render_cmd.add_argument("--from-plan", type=Path, help="Use an already-generated, editable plan JSON")
    render_cmd.add_argument("--max-sync-lag", type=float, default=60)
    render_cmd.add_argument("--width", type=int, default=1920)
    render_cmd.add_argument("--height", type=int, default=1080)
    render_cmd.add_argument("--fps", type=int, default=30)
    render_cmd.add_argument("--no-clean-audio", action="store_true")

    args = parser.parse_args(argv)
    try:
        project = load_project(args.project)
        if args.action == "inspect":
            for name, path in [
                ("lav", project.audio),
                *((camera.name, camera.path) for camera in project.cameras),
                *(([("slides", project.slides.path)] if project.slides else [])),
            ]:
                info = probe(path)
                length = info.get("format", {}).get("duration", "?")
                print(f"{name}: {path} ({length}s)")
            return 0

        if args.action == "render" and args.from_plan:
            plan = EditPlan.load(args.from_plan)
            if Path(plan.audio).resolve() != project.audio.resolve():
                raise ValueError("Edit plan audio does not match this project's microphone")
        else:
            offsets = synchronize(project, max_lag_seconds=args.max_sync_lag)
            print("Synced camera offsets:", offsets, file=sys.stderr)
            plan = make_plan(project, offsets, on_progress=lambda s: print(s, file=sys.stderr))
        if args.action == "plan":
            plan.save(args.output)
            print(f"Plan: {args.output} ({len(plan.shots)} shots)")
            return 0

        dest = args.output.expanduser().resolve()
        if not args.from_plan:
            edit_file = dest.with_suffix(".plan.json")
            if edit_file.exists():
                raise FileExistsError(f"Plan already exists: {edit_file}")
            plan.save(edit_file)
            print(f"Editable timeline: {edit_file}", file=sys.stderr)
        video = render(project, plan, dest, width=args.width, height=args.height,
                       fps=args.fps, clean_audio=not args.no_clean_audio)
        print(f"Video: {video}")
        return 0
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, KeyError) as exc:
        print(f"Photo Finish: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
