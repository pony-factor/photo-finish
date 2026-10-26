# Photo Finish — product vision and development roadmap

_Last reviewed: 2026-10-26. Ordered roadmap, not a claim that the proposed features already exist._

> **North star:** Turn multiple camera recordings of **one presenter** and a separate lavalier microphone into an aesthetically directed, synchronized seminar video. The software should behave like a thoughtful human camera director: choose the right angle, occasionally use a gently moving side crop, and optionally show slides. It must **not edit, transcribe, summarize, or delete what was spoken**.

## 1. Product contract — non-negotiable

1. **Any number of cameras.** “Three cameras” was only an example. No fixed angle count, assumed front/left/right arrangement, or requirement for more than one speaker.
2. **One presenter is the primary use case.** This is not a speaker-diarization podcast tool. Camera choice is informed by framing, movements, prosody, and editorial pacing — not whose turn it is to talk.
3. **The lavalier/master microphone supplies one continuous audio timeline.** Align camera scratch tracks to it, then keep it continuous across *all* visual edits. Audio enhancement may be optional; speech cuts are not.
4. **No transcription by default or as a required stage.** Do not call Whisper, speech-to-text, keyword detection, speaker diarization, or filler-removal services to direct cuts. The system must work without text or verbal semantics.
5. **Do not cut ums, hesitations, quiet passages, pauses, or speech for pacing.** Monotonous delivery may invite an *image change*, never an audio deletion.
6. **Slides are optional.** Cameras-only, cameras + slide capture, and eventually imported PDFs/PPTX are valid. Slides should enrich rather than dictate direction.
7. **Director-quality visual intentions.** Prefer the main/front view for expressive phrases, high-energy vocal inflection and gestures. During long visually/vocally steady passages, a clear side shot with an understated digitally animated crop can refresh composition.
8. **Not random or fixed-interval switching.** Cuts must reflect the whole recording's rhythm, visual continuity, camera safety and likely upcoming events. Favor a composed hold over distracting over-editing.
9. **Preserve source assets and editability.** Originals are immutable. Render a finished movie **and** a human-editable timeline/decision file; show why a cut was proposed and allow overrides.
10. **Local-first, open-source intent.** Analyze and render offline when dependencies/models are installed. Optional advanced models must have license/provenance checks; public repo still needs an explicit open-source license (issue #21).

## 2. Example end-user experience

A presenter records a 75-minute seminar with four cameras, one wireless lavalier and optionally a slide capture. The editor:

1. Imports the camera files, lavalier recording, and optional slides. It does **not** demand a transcript or count the speakers.
2. Checks source quality/duration/timebase. Syncs available camera scratch audio to the lavalier, detects clock drift, and asks for a manual cue only when confidence is low.
3. Examines the opening moments and periodically checks afterward to label shots (main, wide, profile left/right, close-up, alternate, slides). The user may correct any label.
4. Analyzes **how** speech is delivered (energy, intonation, pitch changes, rhythm, quiet periods), plus body movement, gesture, visibility, framing, and slide changes. It does not extract the words.
5. Plans a watchable sequence across *all* available footage. When the speaker becomes animated, favor the main angle; during a steady explanation, choose a visually complementary side shot. Use intelligent crop paths only where they enhance the footage.
6. Shows the proposed edit and relevant signal/decision explanations. The user can lock a camera shot, move a cut, tune “calm vs dynamic,” or disable a slide overlay.
7. Renders one cohesive movie with the **complete aligned lavalier soundtrack**. Optionally exports editable footage/timeline to an NLE.

### Desired camera decisions (illustrative, not hard rules)

| Situation | Preferred decision | Safeguards |
| --- | --- | --- |
| Presenter emphasizes an idea vocally or gestures | Main/front-facing view, preferably already established just before the peak | Avoid cutting off a gesture, or choosing an occluded/unusable main shot |
| Long explanation with limited motion or pitch variation | Tasteful side or alternate angle; optional slow reframing | Use quality and recency; do not cut simply because N seconds passed |
| Presenter moves across the stage | Best camera keeping the person visible, possibly wider | Track full body and keep hands/head inside safe crop |
| Momentary pause, “um,” or hesitation | Retain audio; allow a visual hold or tasteful cut only if justified | Absolutely no silence trimming or transcript-based filler suppression |
| Slide changes or becomes important | Optionally insert readable full slide, picture-in-picture, or speaker + slide layout | No slides lane when none provided; don't infer slide timing from a transcript |
| Another camera is dark, blurry, shaky or blocked | Avoid that source until it recovers | Reject candidate shots with low quality or no coverage |
| A side crop would be distracting | Hold stable framing | Cap pan speed/acceleration and avoid a mechanical perpetual sway |

## 3. Baseline on `main`: v0.1 prototype

Merged [PR #1](https://github.com/pony-factor/photo-finish/pull/1) provides:
- `photo_finish/project.py`: JSON source manifest with an arbitrary number of camera paths, optional slides-video path, role hints and manual offsets.
- `photo_finish/sync.py`: audio-envelope correlation between camera scratch audio and microphone in a limited opening window; no drift model yet.
- `photo_finish/analysis.py`: local pitch/loudness/prosody heuristics plus OpenCV frontal face/framing/sharpness/motion measurements.
- `photo_finish/director.py`: initial gap-checked, editable shot plan favoring a main camera for stronger delivery and alternate angles during steadier periods, with rudimentary slide-change detection.
- `photo_finish/render.py`: FFmpeg cuts, a rudimentary procedural side-crop pan, optional denoise/normalization and one continuous microphone track.
- `photo_finish/cli.py`: `inspect`, `plan`, `render`, and `--from-plan` commands.
- Python tests including a **synthetic** two-angle, 10-second end-to-end render smoke test.

This is **not yet a production-quality AI cinematographer**. It has no GUI; no trained semantic/pose-aware shot director; simple frontal face detection; fixed-offset sync; no native slide deck import; no sophisticated subject-guided crop paths, reliable hour-scale drift handling, color matching or NLE export. The current integration test does not establish artistic quality on real seminar footage. This roadmap describes future work, not implemented behavior.

## 4. Architecture and interfaces

```text
Camera A ... Camera N     Lavalier master            Optional slide capture/deck
          \                    |                               /
           ---- inspect and timebase / provenance / source validation ----
                                      |
                   synchronization maps (offset + drift + confidence)
                                      |
                  +-------------------+-------------------+
                  |                                       |
        visual features                         audio features
   person / pose / gesture /             waveform / pitch / prosody /
    shot quality / framing                 cadence / vocal variation
                  |                                       |
                  +---------- decision signals -----------+
                                      |
                      look-ahead aesthetic shot planner
            main/alternate/slide | composition | crop paths | reasons
                                      |
                       editable, versioned timeline plan
                                      |
                  preview / human overrides / safe validation
                                      |
                  FFmpeg renderer + *continuous lavalier audio*
                                      |
                   MP4 / professional NLE interchange / reports
```

**Time model:** The microphone recording defines global `t=0`. A camera frame at global time `t` maps to its own source clock via a synchronization function, not by trimming or stretching the lavalier. Every interval in `[0, microphone_duration]` must be covered by a valid visual source before export. Account for frame boundaries and VFR explicitly.

**Signal model:** Keep visual camera metadata, opening-shot classifications, time-varying subject/gesture and shot scores, audio prosody curves, slides events, and editorial decisions separate. Avoid conflating “low voice energy” with “speaker stopped talking.” Store confidence and diagnostics, not a transcript.

**Planner:** Consider a look-ahead horizon, shot quality, visibility, vocal expression, body gestures, cut frequency, current shot dwell, recent camera reuse, motion path feasibility and source coverage. Use a legible decision trace, not unexplained randomness or only threshold-triggered switches.

**Rendering:** The camera-angle edit is video-only; the microphone audio is mixed exactly once over the finished picture. Optional lav processing uses DSP and does not edit time. Failed validation must stop an export rather than silently delete speech.

## 5. Prioritized release sequence

These versions denote **target milestones**, not scheduled release dates. Work one reviewable feature at a time with tests. Dependencies are more important than calendar promises.

### v0.2 — Trustworthy foundations (P0)

**Goal:** Correct media and synchronization before advancing AI behavior.

1. [#2 — Preserve every moment of the lavalier and validate edited plans](https://github.com/pony-factor/photo-finish/issues/2): timeline invariant, safe source bounds, corruption prevention and test coverage.
2. [#4 — Source inspection and N-camera timebase support](https://github.com/pony-factor/photo-finish/issues/4): reliable codec, rotation, duration, coverage and VFR handling.
3. [#3 — Drift-aware multicamera synchronization](https://github.com/pony-factor/photo-finish/issues/3): multi-window alignment, offsets, confidence, late starts and manual fallback.
4. [#21 — Open-source license and third-party provenance](https://github.com/pony-factor/photo-finish/issues/21): choose project license and inventory FFmpeg/model licenses before shipping external components.
5. Begin [#19 — Realistic A/V regression and aesthetics corpus](https://github.com/pony-factor/photo-finish/issues/19) immediately; continue expanding it at every phase.

**Exit criteria:** Can reliably ingest 1/3/6+ cameras with mixed timing; fails safely on uncovered stretches, handles drift, and passes real-world synchronization fixtures. No audio seconds are missing.

### v0.3 — Understand the performance (P1)

**Goal:** Recognize *camera roles* and *expression* independently of the words said.

6. [#5 — Camera role/framing and single-presenter classification](https://github.com/pony-factor/photo-finish/issues/5): front vs side/wide/close-up, opening analysis and ongoing track; manual role overrides.
7. [#6 — Transcript-free prosody and rhythm](https://github.com/pony-factor/photo-finish/issues/6): vocal emphasis, intonation variability, sustained uniform delivery and signal confidence.
8. [#7 — Gesture, pose and motion intelligence](https://github.com/pony-factor/photo-finish/issues/7): distinguish speaker movement from camera/background movement.
9. [#8 — Look-ahead multicamera direction](https://github.com/pony-factor/photo-finish/issues/8): prioritize expressive main shots, tasteful side angles in steady sections, continuity and cut cooldowns.

**Exit criteria:** A one-presenter seminar with multiple angles gets a coherent proposal; returning from side angles happens for detectable gestural or vocal reasons, not a timer. No diarization or transcript is required.

### v0.4 — Cinematic intelligence (P2-A)

**Goal:** Make chosen shots *look* intentional as well as well timed.

10. [#10 — Optional local model interfaces and rationale](https://github.com/pony-factor/photo-finish/issues/10): offline vision-model backends with explainable, deterministic fallback; check licenses of weights.
11. [#9 — Subject-aware digital pans and crops](https://github.com/pony-factor/photo-finish/issues/9): eye/face/body-safe eased paths, adjustable crop keyframes and per-shot motion choices.
12. [#14 — Match color, exposure and white balance between cameras](https://github.com/pony-factor/photo-finish/issues/14): consistent footage and SDR/HDR correctness.

**Exit criteria:** Side cutaways have constrained, meaningful reframing with no clipped presenter or arbitrary continual sway; matched cameras don't abruptly shift appearance.

### v0.5 — Presentation finishing (P2-B)

**Goal:** Keep slides optional and the original microphone sounding polished.

13. [#11 — PDF/PPTX and slides video import](https://github.com/pony-factor/photo-finish/issues/11): untimed decks get explicit/manual timing; recorded slide builds stay available.
14. [#12 — Slide-aware full-screen, picture-in-picture and split layouts](https://github.com/pony-factor/photo-finish/issues/12): visual slide events and legibility, without transcript-driven guessing.
15. [#13 — Reversible lavalier restoration and loudness mastering](https://github.com/pony-factor/photo-finish/issues/13): noise/de-reverb/EQ where available, loudness metrics and untouched mode.

**Exit criteria:** A cameras-only talk remains uncluttered; a slides talk presents readable information; lavalier cleanup improves quality without removing utterances or changing time.

### v0.6 — Reviewable desktop editor (P3)

**Goal:** Import, review and export without writing JSON.

16. [#15 — Drag-and-drop local desktop studio](https://github.com/pony-factor/photo-finish/issues/15): Mac-first import, N-camera thumbnails, source roles, sync confidence, preview and export.
17. [#16 — Interactive multicamera timeline](https://github.com/pony-factor/photo-finish/issues/16): override/lock proposed cuts, inspect reasons, tune pacing and edit motion paths without touching microphone contents.
18. [#17 — Editable professional NLE interchange](https://github.com/pony-factor/photo-finish/issues/17): OpenTimelineIO and verified target formats where feasible, plus output presets.

**Exit criteria:** A nontechnical seminar owner can get a first edit offline, change camera decisions manually, then render or take the edit to an NLE.

### v0.7 → v1.0 — Production readiness (P4)

19. [#18 — Apple Silicon and cross-platform performance](https://github.com/pony-factor/photo-finish/issues/18): memory ceilings, feature caches, sparse decoding, hardware acceleration and portable fallback.
20. [#20 — Resumable reliable rendering](https://github.com/pony-factor/photo-finish/issues/20): pause/resume/retry, source relinking, atomic outputs and recovery after interruption.
21. Complete [#19 — Reproducible QA and human-rated visual quality](https://github.com/pony-factor/photo-finish/issues/19): benchmarking and release gate that tests real synchronization/visual quality, not merely an MP4 exists.

**Exit criteria:** Long recordings, arbitrary-angle input, expected failure modes and subjective editorial quality are validated against a published matrix. Builds are reproducible and distributed consistently with open-source/license terms.

## 6. Definition of done and regression gates

Every implementation PR or main-branch feature commit must include **intended behavior + edge-case tests**, be measured where meaningful, and not bypass the non-negotiable product contract.

| Gate | Required check |
| --- | --- |
| No content loss | All original microphone time is present; all ums, hesitations and quiet pauses remain. Test precise timing, not just duration. |
| A/V sync | Measure start, middle and end of long footage against lav; report drift and uncertain mapping. |
| Arbitrary camera count | Test 1, 2, 3, 6+ feeds; differing sources, resolutions and availability. |
| Presenter continuity | Avoid losing face/gesturing hands, awkward crops and cuts during gestures. |
| Realistic editing | Calibrated camera-change rate, limited side-shot frequency, stable main-angle bias, look-ahead and clean cut timing. |
| Slides optional | Same successful pipeline with no slides, captured slides and (after issue #11) native decks. |
| Local privacy | Never upload, transcribe, or derive a textual transcript implicitly; no required hosted API. |
| Repeatability | Same source files/settings/model version yield the same plan; manual overrides survive. |
| Usability | Human preview and reversible changes where UI is available; clear errors before rendering otherwise. |
| Reliability | Media corruption, clipped lav, silent scratch tracks, frame-rate mismatch, missing source, partial recording, crash/restart and output collisions fail safely. |

**Editorial evaluation:** Human review should ask whether the viewer can follow the presentation without camera changes feeling random, whether the presenter is framed well, whether cuts preserve complete gestures, whether digital pans feel motivated, and whether slides are readable. Do not equate lots of cuts with higher quality.

## 7. Incremental contribution/commit plan

- Keep each issue independently implementable where possible. Sequence prerequisites before a cinematic feature depending on them.
- Make **one focused, meaningful commit at a time**: narrow intent, corresponding code/tests, and a descriptive commit message. Do not create empty/placeholder commits.
- Preserve Git history of the v0.1 implementation on `main`; document subsequent enhancements without rewriting earlier commits.
- Use the existing CLI as the stable reference interface while UI integration is built.
- Each feature should be able to fall back gracefully when AI weights, slide content or extra cameras are absent.
- Include benchmark fixtures and failure analysis as the implementation matures; “CI green” on synthetic source clips is a minimum, not proof of cinematic performance.

## 8. Research references (ideas, not imported dependencies)

Review the concepts in [Polysync](https://github.com/jianshuo/polysync) (audio/multicam sync), [Reframe](https://github.com/vxnuaj/reframe) (automatic crop paths), [Montage Agent](https://github.com/OZGE-ai/montage-agent) (timeline-oriented editing), and [Homer Nero](https://github.com/FRAME-26/Homer_nero) (directing/shot scoring). **These are candidate research references only**: verify each repository's behavior, maintenance and precise code/model licenses before reuse. None should dictate speaker-diarization, transcription or content trimming in Photo Finish.

## 9. Out of scope by design

Automatic filler-word removal, silence cuts, speech transcription as an editing prerequisite, mandatory cloud processing, fixed three-camera architecture, multiple speakers as a prerequisite, slide decks as a requirement, and indiscriminate cut frequency optimization. Future optional transcript features, if ever considered, would require a separate explicit opt-in specification and **must not affect the standard transcript-free director**.
