# Photo Finish

**A local, open-source AI-director foundation for recorded seminars.**

Combine any number of camera angles, a separate lavalier/audio-master recording,
and an optional slides video into a polished presentation. The eventual editing
decisions use *vocal delivery and visual composition*, not a transcript.

**Core principles**

- Never transcribe speech or automatically remove ums, pauses, or silence.
- Keep microphone audio continuous even when the video angle changes.
- Do not assume a fixed number of cameras or multiple speakers.
- Slides are optional; a deck can be captured as a video source.
- Let users override automatic camera classifications and sync offsets.
- Run locally; no upload to an external AI service is required.

## Install

Requires Python 3.10+, FFmpeg/ffprobe, and a local video decoding environment.

```sh
python -m pip install -e .
```

## Project format

Paths are relative to the manifest. Omit `slides` if there is no slide feed.
An omitted or `null` camera `offset_seconds` requests automatic audio alignment;
a numerical offset overrides it (positive = camera starts later than mic audio).

```json
{
  "audio": "lav.wav",
  "cameras": [
    {"name": "front", "path": "front.mp4"},
    {"name": "profile", "path": "right.mp4", "role": "side"},
    {"name": "wide", "path": "wide.mp4", "role": "wide"}
  ],
  "slides": {"path": "slides.mp4", "offset_seconds": 0}
}
```

Camera roles: `auto`, `main`, `side`, `wide`, `closeup`.
There is no limit of three cameras. Development is being introduced in small
commits; see the repository history for each independently reviewable layer.
