# Detached GPU transcription offload

Design, 2026-10-15; owner decisions recorded 2026-10-16. Awaiting approval. Measurements: `docs/09-baseline-report.md`.

## 1. Intent and why

Transcription is the only stage of the ClipGen pipeline that is unusable on the
owner's hardware. Measured on job `d31a9105` (82 min source, 2026-10-15):

| Fact | Value | Source |
|---|---|---|
| Host CPU | AMD Athlon Gold 3150U, **2 physical cores**, 15 W | host probe |
| CUDA devices | **0** (AMD integrated GPU) | `runtime_capabilities` |
| CPU actually used by the worker | **2.13 of 4 logical** | `/proc` sample, 20 s |
| Observed real-time factor | **7.5-13x** | live job, first 18 min |
| Stage ETA the app showed | **23 574 s = 6.55 h** | `stage_estimates_json` |
| Remaining stages | cropping 980 s, metadata 100 s | same |

Transcription is ~94% of the wall clock. No configuration change closes that
gap: `whisper_cpu_threads` is already matched to the 2 physical cores (raising
it to 4 buys maybe 20%), and lowering the model or beam size was rejected on
quality grounds (`docs/09` section 4.1, Indonesian TV audio).

**The reason this is worth doing is iteration speed, not output volume.**
A separate finding on 2026-10-15 established that the clips are not being
distributed: 28 Facebook Reels, median 6 views, and the page carries an
unoriginal-content warning. The product must now change shape - clips need
something original added - and every format experiment currently costs 6-13
hours. Cutting that to well under an hour is what makes experimenting possible.

This design does **not** address distribution. It removes the thing that makes
addressing it slow.

## 2. Goals

1. A 60-90 min source is transcribed in well under an hour, at zero recurring cost.
2. The local-first architecture is untouched: render, editor, storage, SQLite,
   FFmpeg and metadata all stay on the laptop.
3. An externally produced transcript passes through exactly the same validation
   as a locally produced one.
4. The existing local CPU path keeps working and stays a first-class fallback.

## 3. Non-goals

- Deploying the ClipGen backend, frontend or pipeline to any host. Free CPU
  tiers are *slower* than this laptop (shared vCPU, sleep-on-idle), so they
  make a CPU-bound 6-hour job worse, not better.
- Speeding up cropping (980 s) or metadata (100 s). Both are acceptable.
- Revisiting model size, beam size or language detection. Already decided.
- Word-level timestamps. Currently `include_word_timestamps=False`; keep it.

## 4. Anti-goals

These would make the work a failure even if it technically runs:

- The local-only path becomes broken, second-class, or untested.
- The laptop must stay awake and connected in lockstep with a remote session.
- A full 157 MB WAV is uploaded per job over a home connection.
- An imported transcript bypasses validation and silently corrupts a job.

## 5. Constraints

- **Kaggle free tier**: ~30 GPU-hours/week (T4/P100), 12 h session cap. It is a
  *notebook*, not an HTTP endpoint. Quota is account-level and can run out.
- **Audio size**: `extract_audio` emits WAV mono 16 kHz, so 82 min is ~157 MB.
- ClipGen runs in Docker locally; the backend has no inbound public address.
- The owner's connection is a home line in Indonesia; upload is the limiting
  direction.

## 6. The seam that already exists

No new transcript contract is needed. The code already has a clean boundary:

- `app/core/pipeline/transcribe.py` - `transcribe()` returns `TranscriptResult`.
- `app/core/timeline.py` - `normalize_segments()` **already accepts dicts with
  `start`/`end` in seconds** (`timeline.py:66`), the exact shape produced by
  `segments_to_json()` (`timeline.py:207`) and stored in `Job.transcript_json`.
- `job_service.py:425` runs every transcript through `normalize_segments` and
  records a `NormalizationReport` (dropped, clamped, reordered,
  repetitions_collapsed).

So an imported transcript enters at the same point, gets the same repair and
rejection logic, and produces the same report. **The interchange format is
`segments_to_json`'s output and nothing else.**

## 7. Shape of the solution

**Detached, three steps.** The job does not block on a remote session.

```
[local]  extract audio -> compress to Opus -> export job-<id>.opus + manifest
[kaggle] notebook: faster-whisper small, float16, T4, language=id -> transcript.json
[local]  import transcript.json -> normalize_segments -> resume pipeline
```

Decoupling matters because a Kaggle session can last up to 12 hours and the
laptop may sleep; nothing should depend on both being alive at once.

### Decisions made here (author's call, not the owner's)

1. **Compress before upload.** Opus mono ~16-24 kbps: 82 min goes from ~157 MB
   to roughly 10 MB. Whisper reads it through FFmpeg, and the source is already
   16 kHz mono speech, so the quality cost is negligible against a 15x smaller
   upload. The local CPU path keeps using the existing WAV.
2. **Interchange format** is the `segments_to_json` shape, plus a small manifest
   carrying `job_id`, `source_duration_seconds`, requested language, model size
   and the audio checksum.
3. **Import validates, never trusts.** Reuse `normalize_segments` unchanged;
   reject on checksum or duration mismatch so a transcript cannot be attached
   to the wrong job.
4. **Manual before automated.** Step one is upload-and-click by hand (~5 min of
   attention per video against 6-13 hours today). A Kaggle API integration
   (`kernels push` / poll / `kernels output`) is a later increment, justified
   only once the manual loop has proven the speed and the transcript quality.

### Left to the builder

- Whether export/import is exposed as an API route, a CLI script, or both.
  The pipeline currently has no endpoint that accepts a transcript; `jobs.py`
  exposes only `list`, `get`, `cancel`, `retry`.
- How a job parked waiting for an external transcript is represented. `Job.status`
  is a plain string column with `STAGE_ORDER` in `models.py:18`, so a new state
  is cheap - but it must not break `_pipeline_progress`, the ETA projection, or
  the startup requeue (`requeue_pending_jobs_on_startup`).
- Notebook hygiene: pinning `faster-whisper`, and keeping `beam_size`,
  `vad_filter` and `language` identical to `config.py` so the GPU transcript is
  comparable to the CPU one.

## 8. Step 0: spike first

Before any of the above is built, settle the premise with a throwaway run:

> Take one source already transcribed locally. Transcribe the same audio on a
> Kaggle T4 with `small`, `beam_size=3`, `language="id"`, `float16`. Record
> wall-clock time and diff the text against the local transcript.

This answers two questions that invalidate the whole design if they go the
wrong way: is it actually ~20x faster, and is the Indonesian transcript at
least as good? `config.py`'s own `gpu_transcription_rtf = 0.35` predicts ~29 min
for an 82-minute source; a T4 should beat that. The spike is throwaway code and
gets no tests.

Note that `docs/09` section 4 recorded decoding loops ("balik balik balik ..."
x20+) on all three model sizes. Those loops cost real time through temperature
fallback, and `transcribe.py:70` sets no `condition_on_previous_text`. Worth
measuring in the same spike, since it may be cheap to fix on both paths.

## 9. Owner decisions (2026-10-16)

| Question | Decision |
|---|---|
| What goes first? | **Transcript reuse first**, then the GPU offload. |
| Is uploading third-party TV audio to the owner's Kaggle account acceptable? | **Yes, no conditions.** No dataset-privacy or auto-delete work; no disclosure screen is required by the owner. |
| How does a job pick the offload path? | **Automatically, when the preflight transcription ETA exceeds a threshold.** |

## 10. Build order

### Phase A - Transcript reuse (local, free, no GPU)

Verified 2026-10-16: `retry_job` (`api/routes/jobs.py`) creates a fresh `Job`
with the same `source_path` but does **not** copy `transcript_json`, and the
backend stores no content hash for sources. A retry or a format re-run therefore
re-pays the whole transcription.

The unit of reuse is a transcript for a given *source*, *language* and
*model size* - changing any of those changes the text. A format experiment
(captions, crop, preset, brief) changes none of them, so it should skip the
transcribe stage entirely and also skip audio extraction.

Left to the builder: the cache key (source file content hash vs. the
`parent_job_id` chain vs. `source_path`), where it is stored, and invalidation
when the source file is replaced. A re-uploaded copy of the same episode gets a
new path, so a content hash is the only key that catches it; hashing a 355 MB
file costs seconds against a 6-13 hour stage.

Phase A alone delivers the goal in section 1 for every episode that has been
transcribed once. It does nothing for the **first** transcription of a new
source - that is what Phases B and C address.

### Phase B - Spike

As section 8, with the following author's calls:

- **Three runs, not one**: local CPU on the WAV; Kaggle GPU on the WAV; Kaggle
  GPU on the Opus file. The Opus-compression assumption in section 7 is the one
  technical claim nobody has measured, so it gets its own run and its own
  attribution if quality drops.
- **Pass bar**: GPU time under 1 hour for the 82-minute source, and the owner
  reads three excerpts of the GPU transcript (including one with music or
  applause) and judges them at least as readable as the local `small` output.
  The repo has no ground-truth transcript (`docs/eval/` holds only a README), so
  a numeric word-error bar would be invented.
- **Who runs it**: the owner holds the Kaggle account and the original audio, so
  the builder's deliverable is a self-contained spike kit (notebook plus a
  comparison script), not a finished feature.

### Phase C - Offload

Built only if Phase B passes. Manual file-drop first (section 7, decision 4).

- **Trigger**: automatic when the preflight `transcribing` estimate exceeds a
  threshold. The threshold is a setting; the default is left to the builder.
- **Opt-in tension (author's call, flagged)**: `docs/02` section 13 requires
  external processing to be opt-in. The owner chose automatic triggering and no
  disclosure conditions. To honour both, a single global switch
  `offload_enabled` exists, **default off**; once the owner turns it on, jobs
  above the threshold are offloaded without a per-job prompt. If the owner would
  rather it be on by default, that is a one-line change.
- **Quota exhausted**: the job is parked with a clear status and a button to run
  it locally on CPU instead. No automatic fallback: the app cannot observe
  Kaggle quota in the manual increment, so "automatic" could only be a timer, and
  a parked job waking at night to hold the single worker (`max_workers=1`) for
  six hours is a real failure mode.
- **`condition_on_previous_text`**: measured in the spike and reported, **not**
  applied here. It would change the local path's output, which Goal 4 protects.
  If the spike shows a large win it becomes its own change.

## 11. Still open

1. Offload threshold default (see Phase C).
2. Whether the Kaggle API integration follows soon after the manual loop. Not
   needed to start; the file-drop is designed so a provider can be swapped in
   later (`docs/02` section 12).
