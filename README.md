# Photo Finish

**A local, open-source, transcript-free automatic camera director for presentations.**

Input an arbitrary number of camera recordings, a separate lavalier/audio-master,
and optionally a recorded slides feed. Photo Finish analyzes vocal dynamics,
camera framing, visible faces, and movement, then switches views while preserving
every spoken word, filler, and pause. It's designed for *one speaker filmed from
multiple angles*, not round-robin switching between people.

## Product vision and roadmap

Photo Finish is designed as an **AI camera director for a single seminar presenter**:
give it any number of cameras (three is only an illustration), a continuous
lavalier microphone recording, and **optionally** a slides video or slide deck.
It should automatically classify viewpoints, align every recording to the
microphone, recognize expressive delivery and gestures, and select visually
composed camera angles. It should return to the main/front camera for emphasis
and use restrained, smoothly reframed side shots during extended explanations.
Slides can appear as full-screen or combined presenter/slide compositions when
helpful.

**Editing the picture is not editing the words:** no transcription, speaker
diarization, filler-word cuts, silence deletion, or forced shortening. The entire
lavalier recording must remain continuous across every video cut.

The present `main` implementation (v0.1 prototype) provides a Python/FFmpeg
CLI and **heuristic** editing, not a fully trained cinematic AI director or a
graphical editor. See the [detailed, issue-linked roadmap](docs/ROADMAP.md) for
what is implemented, what is missing, design constraints, tests and release gates.

| Planned stage | What it delivers | Tracked issues |
| --- | --- | --- |
| **v0.2 — Reliable foundations** | Verified audio preservation, timebase-aware camera ingestion, drift-corrected sync, open-source licensing | [#2](https://github.com/pony-factor/photo-finish/issues/2), [#4](https://github.com/pony-factor/photo-finish/issues/4), [#3](https://github.com/pony-factor/photo-finish/issues/3), [#21](https://github.com/pony-factor/photo-finish/issues/21) |
| **v0.3 — Performance intelligence** | Camera-angle classification, transcript-free vocal emphasis, pose/gesture tracking, look-ahead shot direction | [#5](https://github.com/pony-factor/photo-finish/issues/5)–[#8](https://github.com/pony-factor/photo-finish/issues/8) |
| **v0.4 — Cinematic visuals** | Optional offline vision models, composed pans/zooms, cross-camera color matching | [#10](https://github.com/pony-factor/photo-finish/issues/10), [#9](https://github.com/pony-factor/photo-finish/issues/9), [#14](https://github.com/pony-factor/photo-finish/issues/14) |
| **v0.5 — Slides and audio** | Optional PDF/PPTX/video slides, picture-in-picture, reversible lavalier restoration | [#11](https://github.com/pony-factor/photo-finish/issues/11)–[#13](https://github.com/pony-factor/photo-finish/issues/13) |
| **v0.6 — Review/edit/export** | Drag-and-drop desktop studio, editable multicamera timeline and NLE interchange | [#15](https://github.com/pony-factor/photo-finish/issues/15)–[#17](https://github.com/pony-factor/photo-finish/issues/17) |
| **v0.7–1.0 — Production quality** | Apple Silicon acceleration, resumable renders and realistic audiovisual/editorial QA | [#18](https://github.com/pony-factor/photo-finish/issues/18)–[#20](https://github.com/pony-factor/photo-finish/issues/20) |

Each [feature issue](https://github.com/pony-factor/photo-finish/issues) includes
scope, dependencies and testable acceptance criteria. Issues are proposed
features, not promises of implementation or fixed release dates.

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
