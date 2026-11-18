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
- **Wrong spoken language on real Indonesian content.** The pipeline never
  passed a language to Whisper, so it auto-detected from the first 30 s.
  On an Indonesian TV show ("ARISAN", 51.8 min, music/applause intro)
  `tiny` detected **Catalan (p = 0.45)** and produced Catalan captions and
  titles ("Per què te'n s'ho haurà l'homeament senyori."). Forcing
  `language="id"` on the same 75 s gives Indonesian text, but `tiny` still
  drops much of the speech in noisy TV audio (model comparison in §4.1).
  Fix: per-job `transcript_language` (default `id`), detected language and
  confidence recorded in the job summary, warning on doubtful
  auto-detection.
- Segment-level timing only (`word_timestamps=False`), so caption cues are
  timed proportionally within a segment. Users can correct timing; word
  timestamps are an open option (cost not yet measured).

### 4.1 Whisper model comparison on Indonesian TV audio

First 75 s of the "ARISAN" source (studio music, applause, several
speakers), `language="id"`, CPU int8, beam 3, VAD on, idle machine,
2026-10-11. One sample — indicative, not a benchmark.

| Model | Time for 75 s | Real-time factor | Words | Excerpt |
|---|---|---|---|---|
| `tiny` | 264 s | 3.5× | 57 | "Perlatus lo lo mau menciniun DCS, lo tanpa lagi di Rank Ayan Harisan Mereka." |
| `base` | 449 s | 6.0× | 60 | "Slow dada lagi di Rangkayan … Ari San Marde Kabas … Tapi kita kan main bersama influencer" |
| `small` | 718 s | 9.6× | 62 | "Selamat datang lagi di rangkaian Arisan Merdeka … Besertanya bukan ibu-ibu tapi kita akan main bersama Influencer Top Indonesia" |

- Only `small` produces captions a viewer could read without heavy
  correction on this material; `tiny` is mostly unusable.
- At these factors a 52-minute episode would take roughly 3 h (`tiny`),
  5 h (`base`) or 8 h (`small`) to transcribe on this CPU. Noisy TV audio
  is ~2.5× slower than the clean fixture (`tiny` 1.4× there).
- All three models ended in a decoding loop ("balik balik balik …" ×20+).
  Normalization now collapses runs of more than three identical words to
  two (natural reduplication such as "ibu ibu" is kept) and counts them in
  the job summary (`repetitions_collapsed`).

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
