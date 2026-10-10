# 09 --- Baseline Report

Measured 2026-10-10 on the development machine (Windows 11, Docker Desktop
VM with 4 CPUs / 4.76 GB, CPU-only: no usable CUDA/NVENC in the container,
faster-whisper `tiny`, Ollama `gemma3:4b` on the host). Numbers are single
runs unless stated; treat them as a baseline, not a benchmark.

## 1. Fixture

`backend/tests/fixtures/media/speech_landscape.mp4` — 103.9 s, 480×270,
15 fps, mono AAC, 2.3 MB. Speech is synthesized locally with Windows SAPI
(podcast-style monologue, 15 sentences); frames are FFmpeg `testsrc2`.
Provenance and the other fixtures: `backend/tests/fixtures/media/README.md`.

## 2. Processing time

### Historical jobs in the live database (before this work)

10 completed upload jobs (2.3–68.7 min sources), seconds of processing per
source minute:

| Stage | n | Median | p90 |
|---|---|---|---|
| extracting | 10 | 1.2 | 7.4 |
| transcribing | 10 | 41.6 | 143.9 |
| cropping (social render, all clips) | 8 | 41.3 | 88.4 |
| generating_metadata (all clips) | 10 | 3.0 | 11.9 |

The two longest jobs (68.7 and 51.8 min) took 2.6 h each, ~79 % of it in
transcription. 4 of 15 jobs were cancelled and 1 failed ("Interrupted by
backend restart").

### Fixture runs today

| Run | Pipeline | Conditions | Total | Transcribe | Render (clips) | Metadata |
|---|---|---|---|---|---|---|
| A | old (`beb4a1f`): 3 × 30 s windows, TikTok blur | **CPU contention**: 12 unrelated containers crash-looping on the same VM | 2 503 s | 301 s | 1 760 s (3) | 421 s |
| B | new: 2 candidates ≤ 30 s, TikTok crop, captions | contention removed (crash-looping containers paused/stopped) | 340 s | 149 s | 68 s (2) | 112 s |
| B′ | new: one re-render after editing (20.2 s clip, 1080×1920, captions) | same as B | 33 s | – | 33 s | – |

Run A and B are **not** a like-for-like comparison (different load, clip
count, and blur vs crop); they are reported to show where time goes. The
like-for-like signal is the stage split in run B: transcription 44 %,
metadata 33 %, render 20 %. Real-time factor of Whisper `tiny` here:
149 s / 104 s ≈ 1.4.

## 3. Candidate boundaries

Suggested boundaries vs. the real Whisper transcript of the fixture. A
boundary "cuts a sentence" when it falls inside a transcript segment
(more than 0.2 s from either end).

| Pipeline | Boundaries | Cut a sentence |
|---|---|---|
| old `even-spacing` (run A) | 6 | **5** (e.g. clip 1 ended at 30.0 s inside "…a simple rule. Ship one small thing…") |
| new `transcript-boundary-v1` (run B) | 4 | **0** |

Both new candidates ended on a complete sentence; one opened with a
question ("So here is the question… Why do most side projects never
launch?"), which the explanation states.

## 4. Transcript quality observations

- faster-whisper produced two segments **past the end of the audio**
  (102.2–105.3 s and 106.6–109.4 s for a 103.9 s file), repeating earlier
  sentences — a hallucinated tail. Normalization now clamps/drops them
  (`dropped_invalid: 2` in the job summary).
- Segment-level timing only (`word_timestamps=False`), so caption cues are
  timed proportionally within a segment. Users can correct timing; word
  timestamps are an open option (cost not yet measured).

## 5. Export validation and parity (run B / B′, real FFmpeg)

| Check | Result |
|---|---|
| Output dimensions 1080×1920 | pass (all renders) |
| Duration vs trim | 21.221 s vs 21.170 s expected; 20.221 s vs 20.170 s after edit (Δ 0.05 s; tolerance ±0.35 s) |
| Audio stream present / absent per settings | pass (including silent source and muted export) |
| Caption burn-in at the saved position | band mean abs difference 140 (captions on vs off); rest of the frame 0.0 |
| Caption toggle respected | 0 captions rendered when disabled |
| Atomic publish | old file deleted only after the new one validated; no `.partial` files left |
| Source immutability | SHA-256 of the stored source equals the upload after all edits |

## 6. Reliability baseline

- Startup recovery left one clip in `processing` indefinitely (fixed; the
  live DB clip is now `failed` with `INTERRUPTED`).
- `release-validate.ps1` could not pass (asserted deleted files; fixed).
- No real-media tests existed; now 15 tests render real fixtures and
  `scripts/e2e_real.py` covers the workflow (50 checks passing).

## 7. What to measure next

1. Repeat run B three times on an idle machine and report median/p90.
2. One long source (≥ 45 min) with the new pipeline: transcription and
   candidate generation time, peak memory (`docker stats`).
3. Whisper `base` vs `tiny`: transcription time and caption correction rate
   on the same sources (decide with data, docs/07 §4).
4. Rubric labels for 10–20 sources (docs/04 §3) → `scripts/eval_report.py`.
