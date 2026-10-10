# ClipGen

Personal AI Video Assistant untuk membuat clips dari upload video lokal
atau URL YouTube. ClipGen adalah V1 lokal: backend FastAPI,
frontend Next.js, SQLite storage, ffmpeg/faster-whisper untuk pipeline video,
dan Ollama untuk metadata title/caption/hashtags.

## Status

- Release: `v1.0.0`
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3001` bila port `3000` sedang dipakai
- Mode: local workspace; multi-user opsional melalui `AUTH_ENABLED=true`

## Features

- Upload video lokal dan proses menjadi beberapa klip.
- Queue job dengan progress, ETA per stage, dan ETA keseluruhan.
- YouTube URL support dengan stage download asynchronous.
- Mode YouTube otomatis membuat beberapa klip dengan jarak merata sepanjang video.
- Upload lokal mempertahankan frame/aspect ratio sumber.
- Metadata bisa dipilih Bahasa Indonesia atau English.
- Preview, edit metadata, trim timestamp, feedback relevansi, copy caption, download clip, dan export semua clip ZIP.
- Retry manual yang membuat job turunan, recovery restart aman, ETA yang dikalibrasi dari job sebelumnya, health/metrics, dan Playwright E2E.

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

Untuk ranking klip berbasis makna yang lebih kuat, gunakan model terpisah yang
masih masuk akal untuk perangkat lokal:

```powershell
ollama pull qwen3:8b
```

ClipGen hanya mengirim 8–24 kandidat transcript terbaik ke Ollama dalam satu
request; seluruh podcast tidak dimasukkan ke prompt. Bila Ollama belum running,
model belum di-pull, atau responsnya tidak valid, metadata dan ranking klip akan
fallback tanpa menggagalkan render video.

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

Restore backup (script otomatis membuat backup kondisi saat ini terlebih dahulu):

```powershell
.\scripts\restore-storage.ps1 -ArchivePath .\release-artifacts\backups\clipgen-storage-YYYYMMDD-HHMMSS.zip -Force
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

Retention source dan hasil clip default-nya `0`, artinya tidak pernah dihapus otomatis. Atur `UPLOAD_RETENTION_DAYS` atau `CLIP_RETENTION_DAYS` hanya bila kebijakan retensi memang disetujui.

## Tuning Download YouTube

Dengan `YOUTUBE_REQUIRE_COOKIES=true` (default), file cookies Netscape harus
tersedia sebelum job YouTube bisa dibuat. Untuk Docker Compose:

1. Simpan file cookies yang diekspor dari browser Anda di
   `backend/storage/secrets/youtube-cookies.txt`. Jangan commit atau membagikan isinya.
2. Atur `.env`: `YOUTUBE_COOKIES_PATH=/app/storage/secrets/youtube-cookies.txt`.
   Path ini adalah lokasi **di dalam container**, bukan path Windows.
3. Jika variabel lingkungan berubah, terapkan dengan `docker compose up -d backend`
   saat tidak ada job aktif. Jika path sudah benar dan hanya file yang ditambahkan
   atau diganti, cukup klik **Periksa ulang** pada tab YouTube tanpa restart.

Preflight hanya mengecek keberadaan file lokal dan cooldown; status siap belum
menjamin cookies masih diterima YouTube. Tidak perlu mematikan pemeriksaan cookies
untuk mengatasi file yang belum tersedia.

Upload lokal memakai `MEDIA_PROBE_TIMEOUT_SECONDS=60` per pemeriksaan video/audio.
Pemeriksaan berjalan di luar event loop API. Jika masih timeout, respons menjelaskan
kegagalan pemeriksaan, job tidak dibuat, dan file upload percobaan tersebut dibersihkan.

Stage unduh berjalan dari backend/container ke YouTube, sehingga kecepatan ditentukan oleh koneksi server dan pembatasan CDN YouTube, bukan koneksi browser pengguna. Default baru mengunduh empat fragmen sekaligus dan memilih sumber maksimum 720p.

- `YOUTUBE_DOWNLOAD_CONCURRENT_FRAGMENTS=4`: naikkan bertahap sampai `8` bila koneksi server masih longgar dan YouTube tidak melakukan throttling.
- `YOUTUBE_DOWNLOAD_MAX_HEIGHT=720`: gunakan `1080` untuk prioritas kualitas, atau `0` untuk kualitas terbaik yang tersedia.

## Workflow Short-form

Pilih format TikTok, Reels, YouTube Shorts (9:16), square (1:1), atau landscape (16:9), lalu pilih blur background, crop, zoom, atau split screen. Job otomatis pertama-tama membuat kandidat dari energi audio dan cue transcript, lalu membandingkan kandidat tersebut dengan Ollama memakai enam dimensi: hook, alur mandiri, emosi, spesifik, bisa dikutip, dan potensi diskusi. Alasan dan skornya tersimpan di tiap klip agar hasilnya bisa direview. Ini tetap ranking editorial, bukan jaminan prediksi viral.

Set `RENDER_ACCELERATION=auto` untuk memakai NVENC bila ffmpeg dan GPU NVIDIA tersedia; render otomatis beralih ke CPU bila tidak. Pada Docker, GPU juga harus diekspos ke container melalui runtime NVIDIA.

Untuk video panjang pada CPU, default transkripsi memakai `WHISPER_BEAM_SIZE=3`, `WHISPER_VAD_FILTER=true`, dan `TRANSCRIPTION_TIMEOUT_MULTIPLIER=4.0`. Nilai terakhir mempertahankan hard stop tetapi menghindari penghentian terlalu dini ketika CPU lebih lambat dari ETA. Jangan set `WHISPER_DEVICE=cuda` hanya karena NVENC tersedia: CUDA harus terdeteksi oleh CTranslate2 di dalam container.

## Known Limitations

- Auth lokal bersifat opsional; jangan expose langsung ke internet publik tanpa reverse proxy, HTTPS, dan secret yang aman.
- Queue masih in-process dan memproses satu job pada satu waktu. Job aktif yang terputus saat restart ditandai gagal dan dapat dijalankan ulang secara manual; pekerjaan lama tidak akan otomatis mendahului job baru.
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
