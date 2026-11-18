# 10 --- Implementation Notes (overhaul, Phases 0–3)

What was built against the target specification in `01`–`07`, the decisions
behind it, and what is still open. Audit: `08`. Measurements: `09`.

## 1. Work items

| # | Item | Status | Where |
|---|---|---|---|
| 1 | Checkpoint WIP on a branch, green suite | Done | `beb4a1f` on `overhaul/local-first-editor` |
| 2 | Single documentation source | Done | `01`–`07` kept; blueprint duplicate removed; README links fixed |
| 3 | Repository audit | Done | `08-repository-audit.md` |
| 4 | Baseline measurements | Done (single runs) | `09-baseline-report.md` |
| 5 | Failure taxonomy | Done | `backend/app/core/errors.py`; `jobs.error_code`, `clips.render_error_code`; API `{detail, code}` |
| 6 | Timestamp validation | Done | `backend/app/core/timeline.py` (`normalize_segments`, `validate_clip_range`) |
| 7 | Candidate status + algorithm version | Done | `review_status`, `review_reason`, `algorithm_version`, `position` |
| 8 | Schema versioning + tested migrations | Done | `backend/app/database.py` (`schema_migrations`, migrations 1–2) |
| 9 | Export validation + atomic publish | Done | `backend/app/services/export_validation.py`, `clip_render_service.py` |
| 10 | Canonical edit model | Done | `backend/app/core/edit_model.py`, `frontend/src/lib/editGeometry.ts` |
| 11 | Caption editing P0 | Done | `CaptionPanel.tsx`; ASS burn-in in `render_plan.py` |
| 12 | Trim UX | Done | `TrimPanel.tsx` (playhead, nudges, reset to suggestion, I/O keys) |
| 13 | 9:16 framing | Done (manual focus; no tracking) | `FormatPanel.tsx`, crop focus in `render_plan.py` |
| 14 | Autosave + visible status | Done (+ undo/redo, conflicts) | `frontend/src/hooks/useClipEditor.ts` |
| 15 | Parity + E2E tests | Done | `test_media_integration.py`, `test_pipeline_integration.py`, `scripts/e2e_real.py`, `frontend/e2e/editor.spec.ts`, `frontend/e2e/real-backend.spec.ts` |
| 16 | Score display | Done | Rank + explanation + "bukan prediksi views"; compliance shows "x/y cek lolos" |
| 17 | Rubric + calibration report | Tooling done; **labels pending** | `docs/eval/README.md`, `scripts/eval_report.py` |

P1 items delivered early because they were cheap on top of the edit model:
undo/redo, keyboard shortcuts, audio loudness normalization, duplicate and
reorder candidates.

## 2. Key decisions

- **Extend `jobs`/`clips` instead of new tables.** Avoids migrating live
  data and rewriting every route; mapping in `08` §4.
- **Edits are a versioned document**, stored per clip (`edit_json`,
  `edit_revision`). Every save sends `base_revision`; a stale write returns
  `409 EDIT_CONFLICT` and the UI offers "Muat versi terbaru". Saving never
  renders; rendering always uses the saved revision.
- **Preview plays the original source** in the browser and applies the edit
  with CSS that mirrors the FFmpeg geometry (cover crop with
  `object-position` ≙ `crop=(iw-ow)*focus_x`, caption font
  `font_size × min(w,h)/1080`, same greedy wrap). Disclosed approximations:
  browser font vs DejaVu Sans, CSS blur vs `boxblur`, watermark not drawn in
  preview. If the browser cannot decode the source it falls back to the last
  render and says so.
- **Renders are validated before they replace anything** (exists, non-empty,
  probeable, dimensions, duration ±0.35 s, audio presence, first 2 s
  decodable). A failed render keeps the previous file and the edit; the
  clip stays usable with the error shown.
- **HTTP Range for preview/source.** Starlette 0.27 does not support it; a
  small streaming response was added so the editor can seek in long files.

## 3. Candidate algorithm `transcript-boundary-v1`

Windows start 150 ms before a transcript segment and end 300 ms after one,
so no candidate opens or closes inside a recognized sentence. Signals
(0–1) and weights:

| Signal | Weight | Meaning |
|---|---|---|
| `complete_ending` | 0.30 | Last segment ends with `. ! ? …` |
| `standalone_opening` | 0.20 | First segment does not start with a connector ("and", "but", "jadi", "karena", …) |
| `opening_hook` | 0.20 | Question mark or hook phrase in the opening segment (EN + ID lists) |
| `speech_coverage` | 0.20 | Share of the window that is speech |
| `duration_fit` | 0.10 | Closeness to the middle of the min/max duration |

Selection splits the source into one region per requested clip and takes the
best non-overlapping window per region (preserving the previous "spread
across the video" behaviour), then fills gaps from the global ranking. The
weighted sum only orders candidates within one job; it is never shown as a
percentage. Change the weights only together with a new algorithm version
and re-run the evaluation (`docs/eval/README.md`). Without a transcript the
fallback `even-spacing-v1` is used and the explanation says the boundaries
were not aligned to sentences.

## 4. Policies

- **Caption cues vs trim** (docs/03 §6): cues entirely outside the trim are
  kept in the document but not rendered and are labelled "di luar trim";
  cues crossing a boundary are clamped at render time. Widening the trim
  restores them unchanged.
- **Corrected captions are never overwritten**: regenerating metadata only
  touches title/caption/hashtags. Each transcribed cue keeps
  `original_text`, so correction burden is measurable.
- **Legacy clips** (rendered before this work) get a derived edit with
  captions prepared but **disabled**, because their files contain no
  captions; enabling captions and rendering applies them.
- **Rejecting requires a reason** from the docs/04 taxonomy; rejected clips
  are excluded from the ZIP export.
- **Download marks a clip "exported"** (review status + timestamp).
- **Automatic YouTube mode** stays a clean, caption-free export unless
  captions are requested.
- **Spoken language is chosen, not guessed** (`transcript_language`:
  `id` default, `en`, or `auto`). It is independent of the metadata
  language. With `auto`, the job warns when Whisper's confidence is below
  `WHISPER_LANGUAGE_MIN_PROBABILITY` (0.6) or the language is not id/en/ms.
  Jobs created before this option fall back to `id` when retried.

## 5. Quality gates and results (2026-10-10, re-run 2026-10-11 with `small` + audio language)

| Gate | Command | Result |
|---|---|---|
| Backend unit/API/media tests | `docker exec -w /app clipgen-backend python -m pytest -q` | 172 passed |
| Backend static check | `python -m ruff check app tests --select F,E9` | clean |
| Frontend types + lint + build | `tsc --noEmit`, `pnpm --dir frontend lint`, `next build` | clean |
| Playwright (mocked API) | `pnpm --dir frontend e2e` | 26 passed (13 per viewport: 7 existing + 6 editor; desktop and Pixel 5), 2 skipped (opt-in real spec) |
| Real stack, API level | `python scripts/e2e_real.py` | 51 passed, 0 failed with `small` (471 s; transcription 230 s for 104 s of audio) |
| Real stack, browser | `E2E_REAL_BACKEND=1 pnpm --dir frontend exec playwright test e2e/real-backend.spec.ts` | 1 passed (4.5 min with `small`, production build on :3001): audio language chosen in the UI → upload → candidates → caption + trim edit → render validated 1080×1920 → reopen → download probed |

`scripts/sprint3-validate.ps1` runs the container suite, ruff, lint, type
check, build, and Playwright; `scripts/release-validate.ps1 -RunRealE2E`
adds the real-stack check.

### 5.1 Regression checklist (docs/05 §9)

| Item | Covered by | Result |
|---|---|---|
| Import supported file | e2e_real, real-backend spec | pass |
| Handle unsupported/corrupt file | e2e_real (`SOURCE_UNSUPPORTED`, `SOURCE_CORRUPT`, `AUDIO_MISSING`) | pass |
| Generate/load transcript | e2e_real (real Whisper), pipeline tests (recorded) | pass |
| Generate/load candidates | e2e_real, pipeline tests | pass |
| Accept and reject candidates | e2e_real, editor spec | pass |
| Trim and reset to suggested boundaries | editor spec, real-backend spec | pass |
| Correct caption text | editor spec, e2e_real, real-backend spec | pass |
| Change caption style and position | editor spec, e2e_real (pixel check) | pass |
| Adjust crop | editor spec, e2e_real (`focus_x`) | pass |
| Preview edited clip | editor spec (overlay text/colour at cue time) | pass |
| Export MP4 | e2e_real, real-backend spec | pass |
| Verify dimensions, duration, audio, captions | e2e_real (ffprobe + pixel diff) | pass |
| Reopen project, edits persist | e2e_real (incl. backend restart), real-backend spec | pass |
| Retry after a simulated failure | pipeline tests (failed re-render keeps file; transcription failure keeps source) | pass |
| Source media not modified | e2e_real (SHA-256) | pass |
| Logs without secrets | e2e_real (marker scan), sanitized error details | pass |

Manual checks still recommended before a release: playback in a standard
player, small viewport, keyboard-only navigation, and a long source.

## 6. Known limitations

- **Rank is unvalidated.** No rubric labels exist yet; the rank is a
  transparent heuristic, not evidence of quality (docs/04 §8).
- **Caption timing is proportional within a transcript segment**
  (`word_timestamps=False`); expect manual timing fixes on fast speech.
- **Transcription is slow on CPU.** The default model is `small` (readable
  Indonesian, `09` §4.1) at roughly 5–10× the audio duration: a 52-minute
  TV episode needs about 8 hours. `WHISPER_MODEL_SIZE=tiny` is ~2.7× faster
  but its Indonesian captions need heavy correction. A CUDA-capable
  container would remove most of this cost.
- **Existing transcripts are not re-transcribed automatically.** Jobs
  processed with a wrong language need "Proses ulang", which reprocesses
  the whole source.
- **Preview approximations** listed in §2; the rendered MP4 is the
  reference.
- **No face/speaker tracking**; framing is a manual focus point.
- **Only the latest export is kept per clip**; there is no export history.
- **One job at a time**; a long transcription blocks the queue for hours.
- **Single-user local deployment**; do not expose the API publicly.
- Baseline numbers are single runs on a shared machine (`09` §7 lists what
  to repeat).

## 7. Open questions

1. ~~Is a larger Whisper model worth the time?~~ Decided 2026-10-11: `small`
   by default. Open follow-up: GPU transcription or a faster engine to make
   long episodes practical.
2. Should word timestamps be enabled for caption timing (cost unmeasured)?
3. Keep an export history (ExportJob table) or is "latest export" enough?
4. Which cohort is tested first in the observed beta (docs/06 Phase 4)?
