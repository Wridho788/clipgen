# Backend Setup Guide

## Prerequisites

- Docker & Docker Compose (rekomendasi)
- Atau: Python 3.11+, ffmpeg, libsm6 (kalau setup lokal tanpa Docker)

---

## Option 1: Docker Compose (Recommended)

**Paling simple & isolated:**

```bash
# 1. Clone atau cd ke project root
cd /path/to/video-assistant

# 2. Build dan start backend + frontend
docker compose up -d --build

# 3. Check logs
docker compose logs -f backend

# 4. Test liveness dan readiness
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

**Output:**
```json
{"status": "ok", "version": "1.0.0"}
```

**Default Docker setup:** backend memakai Ollama lokal di host via `http://host.docker.internal:11434`.
Pastikan Ollama desktop/local sudah running dan model yang dipilih sudah ada:

```bash
ollama list
ollama pull gemma3:4b
```

**Optional: jalankan Ollama di container Compose**

```bash
OLLAMA_BASE_URL=http://ollama:11434 docker compose --profile ollama up -d
docker exec clipgen-ollama ollama pull gemma3:4b
```

**Lihat API docs:**
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Frontend: http://localhost:3000

Jika port `3000` sedang dipakai Next.js lokal, jalankan frontend container pada port lain:

```powershell
$env:FRONTEND_HOST_PORT = "3001"
docker compose up -d frontend
```

**Stop:**
```bash
docker compose down
```

**Clean (hapus data):**
```bash
docker compose down -v  # -v untuk remove volumes
```

---

## Option 2: Local Setup (Python venv)

**Kalau prefer tidak pakai Docker:**

### Step 1: Install system dependencies

**macOS:**
```bash
brew install ffmpeg libsm6 opencv
```

**Ubuntu/Debian:**
```bash
sudo apt-get install -y ffmpeg libsm6 libxext6 libxrender-dev
```

**Windows:**
```powershell
# Install ffmpeg: https://ffmpeg.org/download.html
# Atau via scoop: scoop install ffmpeg
```

### Step 2: Setup Python venv

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # macOS/Linux
# atau: venv\Scripts\activate  (Windows)

pip install -r requirements.txt
```

### Step 3: Download Whisper model (optional, auto-download on first use)

```bash
python -c "from faster_whisper import WhisperModel; WhisperModel('tiny')"
# Ini download model tiny, simpan di ~/.cache/huggingface/hub
```

### Step 4: Start Ollama server (separate terminal)

```bash
# Install Ollama: https://ollama.ai
ollama serve

# Di terminal lain: pull model
ollama pull gemma3:4b
```

### Step 5: Run backend

```bash
# Set environment
export OLLAMA_BASE_URL=http://localhost:11434
export WHISPER_MODEL_SIZE=tiny

# Run
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Configuration

Edit `backend/.env` (copy dari `.env.example`):

```env
WHISPER_MODEL_SIZE=tiny  # tiny/base/small/medium (trade-off speed vs quality)
WHISPER_DEVICE=cpu        # atau cuda kalau ada GPU
OLLAMA_MODEL=gemma3:4b    # sesuaikan dengan output `ollama list`
OLLAMA_TIMEOUT_SECONDS=30
OLLAMA_NUM_PREDICT=220
HIGHLIGHT_TOP_N=5         # jumlah clip yang dihasilkan (3-5)
METADATA_DEFAULT_LANGUAGE=id  # id atau en
YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS=900
TEMP_CLEANUP_ENABLED=true
TEMP_CLEANUP_INTERVAL_HOURS=6
TEMP_FILE_RETENTION_HOURS=24
REQUEUE_PENDING_JOBS_ON_STARTUP=true
```

Image backend memasang Deno dan `yt-dlp-ejs` bersama `yt-dlp`. Keduanya diperlukan oleh YouTube saat meminta JavaScript challenge; jangan mengganti `yt-dlp[default]` menjadi instalasi tanpa extra tersebut.

---

## Storage Structure

```
backend/storage/
├── uploads/           # Video input (upload atau YouTube download)
├── clips/             # Hasil clip final (rasio source dipertahankan; subtitle untuk YouTube)
└── temp/              # Audio extract, raw clip, SRT files (auto-cleanup)

app.db                 # SQLite database (jobs + clips metadata)
```

---

## API Endpoints

Semua response JSON, error handling via HTTP status codes.

### Videos (Upload & YouTube)

```bash
# Upload file lokal
curl -X POST http://localhost:8000/api/videos/upload \
  -F "file=@video.mp4"

# Optional per-job overrides: durasi clip 20-45 detik, maksimal 3 clip
curl -X POST http://localhost:8000/api/videos/upload \
  -F "file=@video.mp4" \
  -F "min_clip_seconds=20" \
  -F "max_clip_seconds=45" \
  -F "clip_count=3" \
  -F "metadata_language=en"

# Response:
{
  "job_id": "abc-123",
  "status": "pending",
  "estimated_processing_seconds": 180.0,
  "stage_estimates": {"extracting": 8.0, "transcribing": 90.0}
}

# YouTube URL
curl -X POST http://localhost:8000/api/videos/youtube \
  -d "url=https://youtube.com/watch?v=..." \
  -H "Content-Type: application/x-www-form-urlencoded"

# Response:
{
  "job_id": "def-456",
  "status": "pending"
}

# Preview estimasi untuk video dengan durasi 180 detik
curl "http://localhost:8000/api/videos/estimate?duration_seconds=180&source_type=upload&metadata_language=id"
```

### Jobs (Status polling)

```bash
# Get job status
curl http://localhost:8000/api/jobs/abc-123

# Response:
{
  "id": "abc-123",
  "status": "transcribing",
  "progress": 35,
  "error_message": null,
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:05:00"
}

# List semua job
curl http://localhost:8000/api/jobs

# List job yang failed
curl "http://localhost:8000/api/jobs?status=failed"

# Cancel job
curl -X POST http://localhost:8000/api/jobs/abc-123/cancel

# Retry job terminal tanpa menimpa hasil lama
curl -X POST http://localhost:8000/api/jobs/abc-123/retry
```

### Clips (List, detail, edit, download)

```bash
# List clips dari job
curl http://localhost:8000/api/clips/job/abc-123

# Response:
[
  {
    "id": "clip-1",
    "job_id": "abc-123",
    "start_time": 23.5,
    "end_time": 48.2,
    "title": "Moment Lucu",
    "caption": "Ini adalah ...",
    "hashtags": "[\"funny\", \"moment\"]",
    "status": "ready",
    "file_path": "/app/storage/clips/clip-1_final.mp4"
  }
]

# Get clip detail
curl http://localhost:8000/api/clips/clip-1

# Edit clip metadata
curl -X PATCH http://localhost:8000/api/clips/clip-1 \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Custom Title",
    "caption": "Custom caption",
    "hashtags": ["#custom", "#tags"]
  }'

# Download clip
curl -O http://localhost:8000/api/clips/clip-1/file
# Atau pakai browser: http://localhost:8000/api/clips/clip-1/file

# Preview clip (stream untuk web player)
# <video src="http://localhost:8000/api/clips/clip-1/preview" controls />

# Regenerate title, caption, dan hashtags dari transcript tersimpan
curl -X POST http://localhost:8000/api/clips/clip-1/regenerate-metadata

# Download semua clip siap sebagai ZIP
curl -O http://localhost:8000/api/clips/job/abc-123/archive

# Delete clip
curl -X DELETE http://localhost:8000/api/clips/clip-1
```

---

## Monitoring

### Logs

```bash
# Docker
docker compose logs -f backend
docker compose logs -f ollama

# Rotating application log yang dipersist di host
Get-Content backend/logs/clipgen.log -Wait

# Local
# Check terminal where uvicorn running
```

### Health check

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# Queue, jumlah job/clip per status, dan penggunaan storage
curl http://localhost:8000/api/system/metrics

# Release metadata, feature flags, dan known risks
curl http://localhost:8000/api/system/release

# Ringkasan durasi job selesai dan rata-rata stage pipeline
curl http://localhost:8000/api/system/performance

# Jalankan cleanup temp/intermediate segera
curl -X POST http://localhost:8000/api/system/maintenance/cleanup
```

### Sprint 3 validation

```powershell
.\scripts\sprint3-validate.ps1
.\scripts\release-validate.ps1
```

Script release menjalankan Docker health, backend pytest, frontend lint/build,
Playwright E2E desktop+mobile, metrics, release info, performance baseline,
dan cleanup smoke.

### Startup recovery

Saat backend restart, job dengan status `pending` akan otomatis diantrekan ulang
karena belum masuk pipeline berat. Job yang sudah berada di stage aktif
(`downloading`, `transcribing`, `cutting`, dan sejenisnya) ditandai `failed`
dengan pesan interrupted, lalu bisa dijalankan ulang lewat endpoint retry.

```bash
curl -X POST http://localhost:8000/api/jobs/{job_id}/retry
```

### Database inspection (SQLite)

```bash
# Pakai sqlite3 CLI
sqlite3 backend/storage/app.db

# Lihat jobs
SELECT id, status, progress, error_message FROM jobs;

# Lihat clips
SELECT id, job_id, status, title FROM clips;
```

---

## Troubleshooting

### Ollama connection error
```
Error: Ollama connection failed: Connection refused
```
**Solution:** Pastikan Ollama server running:
- Default Docker backend: jalankan Ollama lokal, lalu cek `ollama list`
- Optional container Ollama: `OLLAMA_BASE_URL=http://ollama:11434 docker compose --profile ollama up -d`
- Local setup: `ollama serve` (separate terminal)

### Ollama metadata timeout
```
Solution: Pakai model lebih kecil atau turunkan batas output
OLLAMA_TIMEOUT_SECONDS=30
OLLAMA_NUM_PREDICT=160
```

### Whisper model terlalu lambat
```
Solution: Ganti ke model lebih kecil
WHISPER_MODEL_SIZE=tiny  # 39MB, tercepat, akurasi rendah
```

### Video file corrupt / tidak ter-recognize ffmpeg
```
Solution: Convert ke MP4 format standard
ffmpeg -i input.avi -c:v libx264 -c:a aac output.mp4
```

### Storage penuh
```
Artefak sementara dan intermediate render dibersihkan otomatis setelah 24 jam.
Atur `TEMP_FILE_RETENTION_HOURS` bila perlu. Hasil clip final dan file upload
tidak dihapus otomatis.

Untuk QA/devops, cleanup manual bisa dipicu:
curl -X POST http://localhost:8000/api/system/maintenance/cleanup
```

### Database locked (concurrent access)
```
Solution: SQLite di-design untuk single-writer. 
Jangan jalankan multiple backend instances.
Kalau perlu multi-instance, upgrade ke Postgres (di ARCHITECTURE.md dijelaskan).
```

---

## Next: Frontend Integration

Backend siap! Sekarang frontend perlu:
1. Call `POST /api/videos/upload` untuk upload
2. Polling `GET /api/jobs/{id}` untuk progress
3. Display clips dari `GET /api/clips/job/{id}`
4. Stream preview dari `GET /api/clips/{id}/preview`
5. Download dari `GET /api/clips/{id}/file`

Lihat `FRONTEND_INTEGRATION.md` untuk detail.
