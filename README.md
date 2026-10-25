# Photo Finish

**A local, open-source, transcript-free automatic camera director for presentations.**

Input an arbitrary number of camera recordings, a separate lavalier/audio-master,
and optionally a recorded slides feed. Photo Finish analyzes vocal dynamics,
camera framing, visible faces, and movement, then switches views while preserving
every spoken word, filler, and pause. It's designed for *one speaker filmed from
multiple angles*, not round-robin switching between people.

## Install

Requires Python 3.10+, FFmpeg and ffprobe available on your PATH.

```sh
python -m pip install -e .
```

## Manifest example

Save as `seminar.json`, with source paths relative to the manifest:

```json
{
  "audio": "lav.wav",
  "cameras": [
    {"name": "front", "path": "front.mp4"},
    {"name": "profile", "path": "right.mp4"},
    {"name": "wide", "path": "wide.mp4"}
  ],
  "slides": {"path": "slide-capture.mp4", "offset_seconds": 0}
}
```

The camera array accepts **one or any larger number of angles**. Slides are
optional; omit the `slides` key when not needed. Slides currently need a
video capture, not a PDF or slide-deck import.

A camera's optional `role` can be `auto` (default), `main`, `side`,
`wide`, or `closeup`. The classifier tries to identify the most frontal,
centered, clear camera at the beginning. Profile views can defeat a simple
face detector, so manual role overrides are available.

Each camera's `offset_seconds` defaults to `null`, meaning synchronize its
scratch audio to the lavalier recording automatically. Use a number to override
sync; **positive** means the camera started later than the microphone. A
camera without scratch audio must have an explicit offset. The slide source
defaults to zero offset; set it manually if its recording starts later.

## Commands

```sh
photo-finish inspect seminar.json
photo-finish plan seminar.json -o seminar-plan.json
photo-finish render seminar.json -o seminar-final.mp4
# Change shot sources and boundaries in the generated plan JSON, then re-render:
photo-finish render seminar.json -o revised.mp4 --from-plan seminar-plan.json
# Disable optional mic cleanup while preserving the same cuts:
photo-finish render seminar.json -o unprocessed.mp4 --no-clean-audio
```

The renderer creates a sibling `*.plan.json` timeline unless `--from-plan`
is specified. All media stays on your machine. FFmpeg denoises and normalizes
the lavalier track without cutting it, even through silence or filler words.
Every shot is a video-only edit. The full microphone recording runs continuously.

## Directing behavior

- Analyze vocal loudness, emphasis, pitch changes, and conversational rhythm,
  **without** converting speech into text.
- Classify camera composition from sampled frames and select a preferred front
  camera; favor it for strong gestures, changes in delivery, and high movement.
- During extended visually and vocally steady periods, switch to other clear
  angles and apply subtle digital crop movement. Return to the main view as
  expression or visual movement rises.
- If slides are provided, notice image changes in their video feed and
  selectively display them; slides never become mandatory.
- Prefer comfortable shot lengths rather than cuts every fixed number of seconds.
- Never remove ums, silences, transitions in speech, or any other speech content.

This is an **initial heuristic/computer-vision implementation**, not a fully
trained semantic cinematography model. It detects frontal faces using OpenCV
and uses DSP features of voice; it does not yet recognize complex body-language
meaning, understand slide semantics, import PowerPoint/PDF, or guarantee
director-quality results for every recording. Source coverage must extend across
the microphone recording; the program refuses to silently delete uncovered audio.

## Development

```sh
python -m pip install -e . pytest
python -m pytest -q
```

Dependencies: NumPy, OpenCV (bundled Haar detector), and the system FFmpeg
executables. No hosted API or transcription service.
