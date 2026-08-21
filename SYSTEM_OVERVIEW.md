# ClipGen — System Overview

Complete guide untuk understand backend structure, deployment, dan frontend integration.

---

## 1. Backend Structure

```
backend/app/
├── __init__.py
├── main.py                      ← FastAPI app + lifespan (startup/shutdown)
├── config.py                    ← Centralized settings (env variables)
├── database.py                  ← SQLAlchemy setup
├── models.py                    ← ORM models (Job, Clip)
├── schemas.py                   ← Pydantic request/response
│
├── core/
│   └── pipeline/                ← processing stages (input → output)
│       ├── audio_extract.py     ├─ video → audio (ffmpeg)
│       ├── transcribe.py        ├─ audio → text+timestamp (Whisper)
│       ├── highlight_detect.py  ├─ text → highlight timepoints (heuristik)
│       ├── clip_cut.py          ├─ video+timestamp → raw clip (frame asli)
│       ├── subtitle_burn.py     ├─ raw clip+subtitle → final clip (YouTube saja)
│       └── metadata_gen.py      └─ text → title/caption/hashtag id/en (Ollama)
│
├── services/
│   ├── job_queue.py             ← In-process async job queue (asyncio.Queue)
│   ├── job_service.py           ← Orchestrator (coordinate stages)
│   ├── maintenance.py           ← Temp/intermediate cleanup worker
│   ├── media_probe.py           ← ffprobe duration/resolution detection
│   └── processing_estimator.py  ← Baseline ETA per source/stage
│
└── api/
    └── routes/
        ├── videos.py            ← POST /upload, POST /youtube
        ├── jobs.py              ← GET status, POST /cancel
        └── clips.py             ← GET list, PATCH metadata, DELETE, GET file
```

### Key Components

**main.py:**
- FastAPI app instance
- Lifespan context (startup: init DB + job queue; shutdown: cleanup)
- CORS middleware (allow localhost:3000 untuk frontend dev)
- Static file serving (`/files/clips/` → video storage)
- Error handlers

**Job Service:**
```python
JobService(job_id, db_session).process()
  ├─ download YouTube source (bila URL)
  ├─ extract_audio()
  ├─ transcribe() + save to DB
  ├─ detect_highlights()
  └─ For each highlight:
      ├─ cut_clip()
      ├─ burn_subtitles() (hanya YouTube)
      ├─ generate_metadata(language)
      └─ Update clip in DB
```

**Job Queue:**
- In-process asyncio.Queue
- Background worker loop
- Enqueue di endpoint, pull di background worker
- Single-writer (tidak perlu distributed queue seperti Celery)
- Startup recovery: `pending` diantrekan ulang, stage aktif ditandai failed dan dapat dijalankan ulang manual

---

## 2. Deployment Strategies

### Option A: Docker Compose (Recommended)

**Simplest, isolated, production-ready untuk single-machine:**

```bash
# Project root
docker compose up -d --build

# Services:
# - backend (port 8000, FastAPI)
# - frontend (port 3000, Next.js)
# - ollama (optional profile, LLM server)
# - Services connected via network
```

**What gets persisted:**
- `backend/storage/` (uploads, clips, database) — mounted as volume
- `ollama-models` (model weights) — Docker volume

**First run:**
- Ollama auto-downloads model (5-8GB, bisa 5-10 menit)
- Database auto-created
- Frontend: `http://localhost:3000`
- Liveness: `curl http://localhost:8000/health/live`
- Readiness: `curl http://localhost:8000/health/ready`

Gunakan `FRONTEND_HOST_PORT=3001` bila port `3000` sedang digunakan server frontend lokal.

**Pros:**
- Zero dependency on host OS (semua di container)
- Easy cleanup: `docker-compose down -v`
- Ready for deployment ke cloud (GCP, AWS, Render, Railway)

**Cons:**
- Perlu Docker installed

---

### Option B: Local Python Setup

**Kalau prefer native tanpa Docker:**

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Separate terminals:
# Terminal 1: Ollama server
ollama serve

# Terminal 2: Backend
python -m uvicorn app.main:app --reload --port 8000
```

**Pros:**
- Debugging lebih mudah (attach debugger langsung)
- Modifikasi code, auto-reload

**Cons:**
- Dependency on host OS (ffmpeg, libsm6, etc harus install manual)
- Harder to reproduce environment (Python version, package conflicts)

---

### Option C: Cloud Deployment (Future)

Untuk multi-user atau production:

```yaml
# docker-compose-prod.yml
services:
  backend:
    # ... same as dev
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/clipgen  # swap SQLite
      - REDIS_URL=redis://redis:6379                                # swap in-process queue
  
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=...
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    
  # ... ollama same
```

**For actual cloud deployment (GCP, AWS, Render, Railway):**
- Use managed PostgreSQL (AWS RDS, GCP Cloud SQL)
- Use managed Redis (ElastiCache, MemoryStore)
- Use container registry (Artifact Registry, ECR)
- Configure environment via secrets management

---

## 3. Frontend Integration

**Frontend = Next.js, Backend = FastAPI**

### Architecture

```
Next.js (port 3000)
  ├─ User upload video
  │  └─ POST /api/videos/upload (FormData)
  │     └─ Backend returns job_id
  │
  ├─ Poll job status every 2 seconds
  │  └─ GET /api/jobs/{job_id}
  │     └─ Status: pending → extracting → transcribing → ... → done
  │
  ├─ When done, fetch clips
  │  └─ GET /api/clips/job/{job_id}
  │
  ├─ Display clip preview (streaming)
  │  └─ <video src="/api/clips/{id}/preview" />
  │
  ├─ Edit metadata
  │  └─ PATCH /api/clips/{id}
  │
  └─ Download
     └─ GET /api/clips/{id}/file
```

### API Client (lib/api.ts)

```typescript
// All HTTP requests ke backend
export const api = {
  uploadVideo,      // POST /api/videos/upload
  youtubeUrl,       // POST /api/videos/youtube
  getJobStatus,     // GET /api/jobs/{id}
  listJobs,         // GET /api/jobs
  cancelJob,        // POST /api/jobs/{id}/cancel
  getClipsByJob,    // GET /api/clips/job/{id}
  getClip,          // GET /api/clips/{id}
  updateClip,       // PATCH /api/clips/{id}
  deleteClip,       // DELETE /api/clips/{id}
  getClipPreviewUrl, // URL helper
  getClipDownloadUrl, // URL helper
}
```

### State Management (Zustand)

```typescript
// store/video.ts
export const useVideoStore = create((set) => ({
  currentJobId: null,
  setCurrentJobId: (id) => set({ currentJobId: id }),
  
  clips: [],
  setClips: (clips) => set({ clips }),
}))
```

### Data Fetching (TanStack Query)

```typescript
// hooks/useJobStatus.ts
export const useJobStatus = (jobId: string) => {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.getJobStatus(jobId),
    refetchInterval: 2000,  // poll every 2 seconds
    enabled: !!jobId,
  })
}
```

### Components

**VideoUpload.tsx:** File input, upload trigger
**JobStatus.tsx:** Progress bar, status display
**ClipCard.tsx:** Video preview, metadata editor, download button
**ClipList.tsx:** Grid/list of all clips from job

---

## 4. Request/Response Flow Example

### Scenario: User upload video → get clips

```
1. USER UPLOADS VIDEO
   ┌─────────────────────────────────────────┐
   │ POST /api/videos/upload                 │
   │ Content-Type: multipart/form-data       │
   │ Body: { "file": <binary video> }        │
   └─────────────────────────────────────────┘
                    ↓
   ┌─────────────────────────────────────────┐
   │ Backend:                                │
   │ 1. Save file to storage/uploads/        │
   │ 2. Create Job record in DB              │
   │ 3. Enqueue to job_queue                 │
   │ Response: { "job_id": "abc-123" }       │
   └─────────────────────────────────────────┘

2. POLL JOB STATUS
   ┌─────────────────────────────────────────┐
   │ GET /api/jobs/abc-123                   │
   │ (repeat every 2 seconds)                │
   └─────────────────────────────────────────┘
   
   Response (while processing):
   {
     "status": "transcribing",
     "progress": 35
   }
   
   Response (done):
   {
     "status": "done",
     "progress": 100
   }

3. FETCH CLIPS
   ┌─────────────────────────────────────────┐
   │ GET /api/clips/job/abc-123              │
   └─────────────────────────────────────────┘
   
   Response:
   [
     {
       "id": "clip-1",
       "title": "Moment Lucu",
       "caption": "...",
       "hashtags": ["#funny", "#moment"],
       "status": "ready",
       "file_path": "/app/storage/clips/clip-1_final.mp4"
     },
     ...
   ]

4. PREVIEW CLIP
   ┌─────────────────────────────────────────┐
   │ <video                                  │
   │   src="/api/clips/clip-1/preview"       │
   │   controls />                           │
   └─────────────────────────────────────────┘
   
   → Browser request GET /api/clips/clip-1/preview
   → Backend stream MP4 file dengan Range header support

5. EDIT METADATA (OPTIONAL)
   ┌─────────────────────────────────────────┐
   │ PATCH /api/clips/clip-1                 │
   │ {                                       │
   │   "title": "Punchline Terbaik",         │
   │   "hashtags": ["#comedy", "#viral"]     │
   │ }                                       │
   └─────────────────────────────────────────┘

6. DOWNLOAD CLIP
   ┌─────────────────────────────────────────┐
   │ GET /api/clips/clip-1/file              │
   │ (browser starts download)               │
   └─────────────────────────────────────────┘
```

---

## 5. Database Schema

**jobs table:**
| Field | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| source_type | TEXT | 'upload' \| 'youtube_url' |
| source_path | TEXT | path file atau URL asal |
| status | TEXT | pending/extracting/done/failed |
| progress | INT | 0-100 |
| error_message | TEXT | kalau failed |
| transcript_json | TEXT | Whisper output (JSON) |
| created_at | DATETIME | |
| updated_at | DATETIME | |

**clips table:**
| Field | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| job_id | FK | refs jobs.id |
| start_time | FLOAT | detik di video asal |
| end_time | FLOAT | detik di video asal |
| highlight_score | FLOAT | skor heuristik (debug) |
| file_path | TEXT | path /app/storage/clips/xxx_final.mp4 |
| title | TEXT | AI-generated atau user-edited |
| caption | TEXT | AI-generated |
| hashtags | TEXT | JSON array string |
| status | TEXT | processing/ready/failed |
| created_at | DATETIME | |

---

## 6. Environment & Configuration

### .env (backend)

```env
# Whisper
WHISPER_MODEL_SIZE=base  # tiny/base/small (trade-off speed vs accuracy)
WHISPER_DEVICE=cpu       # cpu atau cuda (kalau ada GPU)

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2    # atau llama2, mistral

# Highlight
HIGHLIGHT_TOP_N=5        # jumlah clip yang dihasilkan

# Output clips keep the source frame/aspect ratio. Vertical crop is skipped.
```

### .env.local (frontend)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 7. Health Checks & Monitoring

**Backend health:**
```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

**Operational metrics:**
```bash
curl http://localhost:8000/api/system/metrics
curl http://localhost:8000/api/system/release
curl http://localhost:8000/api/system/performance
curl -X POST http://localhost:8000/api/system/maintenance/cleanup
```

**Ollama health:**
```bash
curl http://localhost:11434/api/tags
```

**Database:**
```bash
sqlite3 backend/storage/app.db "SELECT COUNT(*) FROM jobs;"
```

---

## 8. Troubleshooting Checklist

| Issue | Diagnosis | Fix |
|---|---|---|
| "Ollama connection refused" | Ollama server not running | `docker-compose up ollama` atau `ollama serve` |
| "Whisper model too slow" | Model size terlalu besar | Set `WHISPER_MODEL_SIZE=tiny` |
| "Video file not recognized" | ffmpeg error | Convert ke MP4: `ffmpeg -i input.avi -c:v libx264 output.mp4` |
| "Frontend 404 on /api/videos/upload" | Backend not running atau CORS issue | Check `http://localhost:8000/docs` untuk test API |
| "Subtitle burned but not visible" | Font size/color issue di ffmpeg | Edit `subtitle_burn.py` filter parameter |
| "Database locked" | SQLite concurrent write | Don't run multiple backend instances |

---

## 9. Next Steps

1. **Backend Setup** → `BACKEND_SETUP.md`
2. **Frontend Setup** → Create Next.js project + use code di `FRONTEND_INTEGRATION.md`
3. **Integration Test** → Upload video → check job status → download clip
4. **Deploy** → Docker Compose atau cloud

---

**End of System Overview**

Untuk detail implementation, lihat:
- `backend/app/main.py` — FastAPI setup
- `backend/app/services/job_service.py` — Pipeline orchestration
- `FRONTEND_INTEGRATION.md` — React/Next.js integration
