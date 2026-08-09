# ClipGen

Personal AI Video Assistant untuk membuat highlight clips dari upload video lokal
atau URL YouTube. ClipGen adalah MVP lokal single-user: backend FastAPI,
frontend Next.js, SQLite storage, ffmpeg/faster-whisper untuk pipeline video,
dan Ollama untuk metadata title/caption/hashtags.

## Status

- Release: `v1.0.0`
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3001` bila port `3000` sedang dipakai
- Mode: local single-user MVP

## Features

- Upload video lokal dan proses jadi beberapa highlight clip.
- Queue job dengan progress, ETA per stage, dan ETA keseluruhan.
- YouTube URL support dengan stage download asynchronous.
- Subtitle hanya untuk job YouTube.
- Upload lokal mempertahankan frame/aspect ratio sumber.
- Metadata bisa dipilih Bahasa Indonesia atau English.
- Preview, edit metadata, copy caption, download clip, dan export semua clip ZIP.
- Health, metrics, performance baseline, cleanup maintenance, dan Playwright E2E.

## Quick Start

Pastikan Docker Desktop sudah running.

```powershell
$env:FRONTEND_HOST_PORT = "3001"
docker compose up -d --build backend frontend
```

Cek:

```powershell
curl.exe http://localhost:8000/health/ready
curl.exe http://localhost:8000/api/system/release
curl.exe http://localhost:3001
```

Buka frontend:

```text
http://localhost:3001
```

## Ollama

Default backend Docker memakai Ollama lokal di host:

```powershell
ollama list
ollama pull gemma3:4b
```

Jika Ollama belum running, metadata generation akan fallback, tetapi pipeline video
tetap bisa berjalan.

## Validation

Sprint 4 release validation:

```powershell
.\scripts\release-validate.ps1 -SkipPlaywrightInstall
```

Tanpa skip, script akan memastikan browser Playwright Chromium tersedia:

```powershell
.\scripts\release-validate.ps1
```

Yang dicek:

- Docker Compose config dan health.
- Backend pytest.
- Frontend lint/build.
- Playwright E2E desktop + mobile.
- API metrics, performance, release info, dan cleanup smoke.

## Common Commands

```powershell
docker compose logs -f backend
docker compose logs -f frontend
curl.exe http://localhost:8000/api/system/metrics
curl.exe http://localhost:8000/api/system/performance
curl.exe -X POST http://localhost:8000/api/system/maintenance/cleanup
```

Backup data lokal:

```powershell
.\scripts\backup-storage.ps1
```

Export release docs/package:

```powershell
.\scripts\export-release-package.ps1
```

## Storage

Data user disimpan di:

```text
backend/storage/
```

Isi penting:

- `app.db`: SQLite database job/clip metadata.
- `uploads/`: source video yang sudah di-upload/download.
- `clips/`: hasil clip final.
- `temp/`: file sementara dan intermediate.

Jalankan backup sebelum cleanup besar atau sebelum memindahkan project.

## Known Limitations

- Belum ada auth; jangan expose langsung ke internet publik.
- Queue masih in-process; job `pending` bisa diantrekan ulang saat startup, tetapi
  job aktif yang terputus perlu retry.
- YouTube extraction bergantung pada ketersediaan dan perubahan platform sumber.
- Video panjang CPU-bound bisa butuh resource Docker lebih besar.

## Documentation

- [Release Notes](RELEASE_NOTES.md)
- [Release Checklist](RELEASE_CHECKLIST.md)
- [Sprint 4 Readiness](SPRINT4_RELEASE_READINESS.md)
- [Architecture](ARCHITECTURE.md)
- [System Overview](SYSTEM_OVERVIEW.md)
- [Backend Setup](BACKEND_SETUP.md)
- [Sprint 3 QA Checklist](SPRINT3_QA_CHECKLIST.md)
