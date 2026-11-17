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

- Upload video lokal (MP4/MOV/MKV/WebM) atau URL YouTube; queue job dengan progress dan ETA per stage.
- Transkrip Whisper lokal yang dinormalisasi (urutan, batas durasi, segmen halusinasi di luar audio dibuang). **Bahasa audio** dipilih per job (default Indonesia; English atau deteksi otomatis) — terpisah dari bahasa metadata. Deteksi otomatis yang ragu memberi peringatan di job.
- Kandidat klip dipotong **di batas kalimat transkrip** (`transcript-boundary-v1`) dan tetap tersebar sepanjang video, dengan alasan yang bisa dibaca dan peringkat relatif — bukan persen atau prediksi viral.
- Editor klip: preview langsung dari video sumber, trim dari playhead (I/O), reset ke saran AI, caption dari transkrip yang bisa diedit (teks, timing, ukuran, warna, outline/kotak, posisi), framing/crop, audio & normalisasi, watermark.
- Autosave dengan status terlihat, deteksi konflik versi, undo/redo, shortcut keyboard.
- Review kandidat: terima, tolak dengan alasan, duplikat, ubah urutan.
- Export MP4 dari edit yang tersimpan, divalidasi (dimensi, durasi, audio, decode) sebelum mengganti file lama; render gagal tidak menghapus edit atau file sebelumnya.
- Kode error stabil (mis. `SOURCE_CORRUPT`, `AUDIO_MISSING`, `EXPORT_VALIDATION_FAILED`) di API dan UI.
- Metadata Bahasa Indonesia/English via Ollama (opsional, fallback bila tidak tersedia), paket distribusi, campaign brief.
- Migrasi schema bernomor, recovery restart, retry job, health/metrics.

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

## Metadata AI: Ollama atau Gemini

Default backend Docker memakai Ollama lokal di host:

```powershell
ollama list
ollama pull gemma3:4b
```

Ollama hanya dipakai untuk judul, caption distribusi, dan hashtag per klip;
pemilihan kandidat berjalan lokal tanpa LLM. Bila Ollama belum running, model
belum di-pull, atau responsnya tidak valid, metadata akan fallback tanpa
menggagalkan render video.

Untuk memakai Gemini Developer API pada free tier:

1. Buat API key di [Google AI Studio](https://aistudio.google.com/apikey).
2. Simpan key hanya di `.env` lokal (jangan commit atau kirim lewat frontend):

   ```dotenv
   METADATA_PROVIDER=gemini
   GEMINI_API_KEY=your-key
   GEMINI_MODEL=gemini-3.8-flash
   ```

3. Jalankan ulang backend dengan `docker compose up -d --build backend`.

Gemini dipakai untuk metadata saja; Whisper dan pemilihan kandidat tetap lokal.
Jika API key kosong, kuota habis, atau Gemini gagal, ClipGen tetap menghasilkan
metadata fallback dan render video tetap berjalan. Free tier punya batas kuota
yang dapat berubah. Transkrip dikirim ke Google untuk generasi metadata; tinjau
[ketentuan Gemini API](https://ai.google.dev/gemini-api/terms) sebelum memakai
transkrip privat. Google menyatakan konten di free tier dapat digunakan untuk
meningkatkan produk mereka. Detail harga dan model aktif ada di
[pricing Gemini API](https://ai.google.dev/gemini-api/docs/pricing).

## Validation

Release validation — Compose health, backend pytest + ruff di container, frontend lint/type-check/build, Playwright desktop + mobile, smoke endpoint:

```powershell
.\scripts\release-validate.ps1 -SkipPlaywrightInstall
```

Tambahkan workflow nyata end-to-end (Whisper + FFmpeg + Ollama, beberapa menit):

```powershell
.\scripts\release-validate.ps1 -SkipPlaywrightInstall -RunRealE2E
```

Perintah terpisah:

```powershell
# Backend: unit, API, dan render FFmpeg sungguhan dengan fixture
docker cp backend/tests clipgen-backend:/app/tests; docker cp backend/pytest.ini clipgen-backend:/app/pytest.ini
docker exec -w /app clipgen-backend python -m pytest -q                   # semua
docker exec -w /app clipgen-backend python -m pytest -q -m "not media"    # cepat, tanpa render

# Workflow nyata via API (laporan JSON di release-artifacts/e2e/)
python scripts/e2e_real.py

# Workflow nyata via browser (stack harus running)
$env:E2E_REAL_BACKEND = "1"; pnpm --dir frontend exec playwright test e2e/real-backend.spec.ts

# Evaluasi kualitas klip (lihat docs/eval/README.md)
python scripts/eval_report.py report
```

Fixture media legal ada di `backend/tests/fixtures/media/` (buat ulang dengan `scripts/make-media-fixtures.ps1`).

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

1. Upload → pilih format (TikTok/Reels/Shorts 9:16, square, landscape, atau original) dan cara mengisi kanvas (crop, zoom, blur, split).
2. Job membuat transkrip, lalu kandidat di batas kalimat. Tiap kandidat menyimpan sinyal (`complete_ending`, `standalone_opening`, `opening_hook`, `speech_coverage`, `duration_fit`) beserta penjelasannya. Peringkat hanya mengurutkan kandidat dalam satu job — bukan prediksi views.
3. Buka kandidat di editor: trim, koreksi caption, atur framing. Edit tersimpan otomatis sebagai dokumen edit (milidetik); video sumber tidak pernah diubah.
4. **Render edit** → file divalidasi → download. Detail desain: `docs/10-implementation-notes.md`.

Set `RENDER_ACCELERATION=auto` untuk memakai NVENC bila ffmpeg dan GPU NVIDIA tersedia; render otomatis beralih ke CPU bila tidak. Pada Docker, GPU juga harus diekspos ke container melalui runtime NVIDIA.

Default bahasa audio untuk job baru diatur dengan `WHISPER_LANGUAGE` (`id`, `en`, atau `auto`). Jangan pakai `auto` untuk acara TV/podcast yang dibuka dengan musik: Whisper menebak bahasa dari 30 detik pertama dan pernah membaca acara Indonesia sebagai bahasa Katalan.

Untuk video panjang pada CPU, default transkripsi memakai `WHISPER_BEAM_SIZE=3`, `WHISPER_VAD_FILTER=true`, dan `TRANSCRIPTION_TIMEOUT_MULTIPLIER=4.0`. Nilai terakhir mempertahankan hard stop tetapi menghindari penghentian terlalu dini ketika CPU lebih lambat dari ETA. Jangan set `WHISPER_DEVICE=cuda` hanya karena NVENC tersedia: CUDA harus terdeteksi oleh CTranslate2 di dalam container.

## Known Limitations

- Peringkat kandidat belum divalidasi dengan label manusia; perlakukan sebagai heuristik transparan (lihat `docs/eval/README.md`).
- Timing caption dibagi proporsional per segmen transkrip (tanpa word timestamps); ucapan cepat mungkin perlu koreksi timing.
- Preview editor adalah perkiraan (font browser, blur, watermark); MP4 hasil render adalah acuan.
- Belum ada tracking wajah otomatis; framing memakai titik fokus manual.
- Auth lokal bersifat opsional; jangan expose langsung ke internet publik tanpa reverse proxy, HTTPS, dan secret yang aman.
- Queue masih in-process dan memproses satu job pada satu waktu. Job aktif yang terputus saat restart ditandai gagal dan dapat dijalankan ulang secara manual.
- YouTube extraction bergantung pada ketersediaan dan perubahan platform sumber.
- Transkripsi CPU dengan Whisper `small` (default) kira-kira 5–10× durasi audio — episode 52 menit ±8 jam. `WHISPER_MODEL_SIZE=tiny` ±2,7× lebih cepat tetapi transkrip bahasa Indonesia-nya hampir tidak terbaca. GPU CUDA di container akan memangkas waktu ini drastis.

Daftar lengkap: `docs/10-implementation-notes.md` §6.

## Documentation

- [Overhaul documentation pack](docs/README.md) — spesifikasi (`01`–`07`), audit (`08`), baseline (`09`), catatan implementasi (`10`)
- [Clip-quality evaluation kit](docs/eval/README.md)
- [System Overview](docs/SYSTEM_OVERVIEW.md)
- [Performance & Reliability Runbook](docs/V1_PERFORMANCE_AND_RELIABILITY_RUNBOOK.md)
- [Campaign Brief Runbook](docs/CAMPAIGN_BRIEF_RUNBOOK.md)
