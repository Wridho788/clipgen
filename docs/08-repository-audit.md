# 08 --- Repository Audit

**Audited:** branch `overhaul/local-first-editor`, starting from commit
`beb4a1f` (checkpoint of the uncommitted work on top of `6672a72`), on
2026-10-10. Checklist from `07-decisions-and-open-questions.md` §3.

This audit records what existed *before* the overhaul changes, what was
kept, and why the migration path was chosen. Measurements are in
`09-baseline-report.md`; what changed is in `10-implementation-notes.md`.

## 1. Checklist

| Item | Finding |
|---|---|
| Repository / branch / commit | Local git repo, `master` → `overhaul/local-first-editor`; audit base `beb4a1f`. |
| Languages & frameworks | Backend Python 3.11 (container), FastAPI 0.104, SQLAlchemy 2.0, Pydantic 2.5, Starlette 0.27. Frontend Next.js 14.2 (App Router), React 18, TanStack Query 5, Tailwind 3, TypeScript 5. |
| Package managers / runtimes | pip (`backend/requirements.txt`), pnpm 11 workspace (`frontend/`), Node 22 on the host. Docker Compose for the stack. |
| Entry points | `backend/app/main.py` (FastAPI app, lifespan: DB init → recovery → in-process queue worker → maintenance loop). `frontend/src/app/page.tsx` (upload/queue), `frontend/src/app/jobs/[id]/page.tsx` (job + clips). |
| Module boundaries | Routes (`app/api/routes/*`) → services (`app/services/*`: job orchestration, queue, estimator, YouTube, maintenance) → pipeline adapters (`app/core/pipeline/*`: audio extract, Whisper transcribe, FFmpeg cut/social render, Ollama metadata). UI never calls FFmpeg directly — boundary already matched docs/02 §2. |
| Transcription engine | faster-whisper `tiny` (default), CPU int8 in an isolated `spawn` process with progress events and a killable timeout. `word_timestamps=False`. VAD on, beam 3. |
| Candidate generation & scoring | **None at audit time.** The WIP had removed highlight detection; `JobService._plan_clip_windows` produced evenly spaced fixed-length windows. `highlight_score` was a legacy column always `0.0`. The previous (deleted) detector produced the ">100%" score referenced in docs/04 §1. |
| Media processing / rendering | FFmpeg via argument arrays (no shell). One pass `-ss … -i … -t …` with a social filter graph (crop/zoom/blur/split) and optional drawtext watermark; NVENC auto-detected with libx264 fallback. Output written directly into `storage/clips/` with no post-render validation. |
| Captions / subtitles | **Removed in the WIP** (`subtitle_burn.py` deleted). No caption editing or burn-in existed. Only the watermark used `drawtext`. |
| Storage & persistence | SQLite (`backend/storage/app.db`, WAL) for jobs/clips/users/feedback; files under `storage/uploads`, `storage/clips`, `storage/temp`. Schema changes via ad-hoc `ALTER TABLE` in `init_db`, no version record. Times stored as float seconds. |
| Editor controls | Metadata edit (title/caption/hashtags), numeric trim (seconds) that re-rendered immediately, thumbs-up/down feedback, delete, download, ZIP. No preview of edits before render, no captions, no framing, no autosave, no undo. |
| Deployment / build | `docker compose up -d --build backend frontend`; backend bind-mounts `./backend/app` (code changes need a container restart, no rebuild). Frontend image built with `NEXT_PUBLIC_API_URL`. |
| Tests / lint / build | Backend pytest (84 tests, 1 stale failure for the removed `ClipResponse.analysis`), run inside the container (tests are not in the image). Frontend `next lint` + `tsc` clean; Playwright 7 tests, all with a mocked API. No real-media test, no fixtures. |
| External APIs & credentials | Ollama on the host (`gemma3:4b`) for titles/captions/hashtags — optional, falls back. yt-dlp for YouTube with a Netscape cookies file in `storage/secrets/` (git-ignored). Optional local auth with `AUTH_SECRET_KEY`. No paid services. |
| Known bugs (reproduced) | (1) A trim re-render interrupted by a restart left the clip in `processing` forever (one such clip in the live DB). (2) `scripts/release-validate.ps1` asserted files deleted by the WIP and could not pass. (3) Root `README.md` linked to six deleted documents. (4) Starlette 0.27 `FileResponse` ignores `Range`, so `<video>` seeking in long files was unreliable. (5) Whisper output for the test fixture contained segments past the end of the audio (hallucinated repeat). |

## 2. Feature inventory

| Area | Decision | Rationale |
|---|---|---|
| In-process job queue, heartbeats, ETA calibration, cancellation, startup recovery | **Keep** | Works, tested, matches "jobs not UI-thread work" (docs/02 §8). Recovery extended for interrupted re-renders. |
| Whisper isolation process | **Keep** | Killable, reports progress, already behind a function boundary. |
| Social render filters / NVENC fallback | **Refactor** | Logic reused, but moved behind one render plan built from the saved edit so preview and export share geometry. |
| Evenly spaced windows | **Replace** (keep as fallback) | Fixed slicing cut sentences at 5 of 6 boundaries on the fixture (`09` §3). Kept as `even-spacing-v1` when no transcript exists. |
| Ad-hoc `ALTER TABLE` upgrades | **Replace** | Numbered, recorded, tested migrations (docs/02 §6). |
| Trim endpoint | **Refactor** | Kept for compatibility; now updates the canonical edit then renders it. |
| Metadata generation, distribution pack, campaign briefs/compliance | **Keep** | Out of the overhaul's scope; compliance percentage display changed to "x/y checks". |
| YouTube intake, cookies gate | **Keep** | Unrelated to the editor path; untouched. |
| Clip feedback (±1) | **Keep** | Complements the new review status; both feed evaluation. |
| Root/sprint documents removed in the WIP | **Remove** (already) | Superseded by `docs/01`–`10`. |
| `docs/clipgen-overhaul-blueprint.md` | **Remove** | Verbatim concatenation of `01`–`07`; kept the split files as the single source. |

## 3. Decisions taken after the audit (docs/07 §4)

| Question | Decision | Why |
|---|---|---|
| Keep the current framework? | **Yes** — FastAPI + Next.js. | Both work; the editor gap was missing data model and UI, not the framework. |
| Browser-only, desktop wrapper, or local companion worker? | **Keep the local backend as the worker** (Docker on the same machine). | It already is a local companion process with FFmpeg/Whisper; the browser only previews. A desktop wrapper adds packaging work without solving a measured problem. |
| Transcription engine/model | **faster-whisper, default changed `tiny` → `small` (2026-10-11)**, with an explicit spoken language (`id` default) and normalization after it. | `tiny` was fastest (RTF ≈ 1.4 on clean speech, 3.5 on TV audio) but produced unreadable Indonesian and, without a language, mis-detected an Indonesian show as Catalan. `small` was the first size with readable Indonesian captions (`09` §4.1); accepted cost ≈ 2.7× `tiny` (owner's decision). ETA and the transcription timeout were rescaled per model. |
| Repair or replace scoring? | **Replace** with a transparent, versioned heuristic (`transcript-boundary-v1`). | The old score was deleted and was never validated; the new rank is explicitly a ranking signal (docs/04 §5) pending rubric labels. |
| Rendering in-process or worker? | **Same queue worker**, one job at a time. | Matches the single-user local deployment; render ~33 s per 20 s clip at 1080×1920 on CPU. |
| Database/storage | **SQLite + files**, extended rather than split. | See §4. |
| Export presets | **Keep the six existing presets**; validated per render. | All six pass dimension/duration/audio validation in tests. |
| Cloud processing for the first beta? | **No.** | No measured bottleneck that local hardware cannot handle for 1–2 h sources yet. |

## 4. Data model mapping (blueprint → repository)

The blueprint's entities (docs/02 §5) were mapped onto the existing tables
instead of introducing new ones, to avoid a data migration of live user data
and a rewrite of every route:

| Blueprint entity | Implemented as |
|---|---|
| Project + SourceAsset | `jobs` row (source path/name/duration/size, options, status, `error_code`). |
| TranscriptSegment | `jobs.transcript_json` (normalized, seconds); integer-ms objects in memory (`app/core/timeline.py`). |
| ClipCandidate | `clips` row: `suggested_start/end_time`, `analysis_json` (signals, explanation, rank), `algorithm_version`, `review_status`, `review_reason`, `position`. |
| ClipEdit | `clips.edit_json` (`app/core/edit_model.py`, integer ms, `schema_version`) + `edit_revision`. |
| ExportJob | Latest export only: `clips.status`, `rendered_revision`, `render_report_json`, `render_error_code/message`, `exported_at`. A history of exports is not kept (open question in `10` §6). |

Splitting these into separate tables remains possible later; the edit
document is versioned independently of the database schema.
