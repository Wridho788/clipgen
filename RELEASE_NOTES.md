# ClipGen v1.0.0 Release Notes

Release date: 2026-08-09

## Summary

ClipGen v1.0.0 is the first local MVP release. It supports local video upload,
YouTube URL processing, stage-level progress/ETA, clip preview/download, metadata
editing, and local Docker-based validation.

## Product Highlights

- Local upload flow with browser upload progress and upload ETA.
- YouTube URL flow creates a job immediately, then downloads in the worker.
- Pipeline progress includes extraction, transcription, highlight detection,
  cutting, YouTube subtitle burn, and metadata generation.
- Local uploads keep the original aspect ratio and do not burn subtitles.
- YouTube clips can include subtitles.
- Metadata language can be Indonesia or English per job.
- Clip result page supports preview, edit metadata, copy caption, download single
  clip, and download ready clips as ZIP.

## Backend

- FastAPI release version is `1.0.0`.
- Startup recovery requeues safe `pending` jobs and marks interrupted active jobs
  failed with a retryable message.
- `/api/system/metrics` exposes queue, job/clip counts, and storage usage.
- `/api/system/performance` summarizes completed job durations and stage timings.
- `/api/system/release` exposes release metadata, feature flags, and known risks.
- `/api/system/maintenance/cleanup` runs temp/intermediate cleanup manually.
- YouTube downloader uses yt-dlp with Deno/JS challenge support and fallback
  extractor args.

## Frontend

- Next.js upgraded to `14.2.35`.
- Dashboard includes release/system status: version, worker state, queue, storage.
- Clip preview layout no longer assumes vertical output.
- Playwright E2E covers dashboard YouTube flow and result page metadata editing on
  desktop and mobile.

## DevOps

- Docker Compose builds backend and frontend.
- `scripts/sprint3-validate.ps1` runs technical QA checks.
- `scripts/release-validate.ps1` runs release readiness validation.
- `scripts/backup-storage.ps1` creates a local storage backup ZIP.
- `scripts/export-release-package.ps1` exports release docs/package artifacts.
- CI includes backend tests, frontend lint/build, Playwright E2E, and compose config.

## Validation Snapshot

Latest local validation:

- Backend pytest: `33 passed`
- Frontend lint: passed
- Frontend build: passed
- Playwright E2E: `4 passed`
- Docker backend/frontend: healthy
- Backend ready endpoint: HTTP 200
- Frontend root: HTTP 200

## Known Risks

- YouTube availability can change because extraction depends on the source platform.
- Active jobs are retryable after interruption but not resumable from exact pipeline
  checkpoints.
- Long videos can be CPU/memory heavy; monitor Docker resource usage.
- This release has no auth and is intended for local/private use only.
