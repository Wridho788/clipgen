# ClipGen Project — Complete Summary, Execution Roadmap & Future Vision

> Status: legacy planning document. ClipGen has moved to MVP `v1.0.0`.
> For the current release source of truth, use `README.md`,
> `RELEASE_NOTES.md`, `RELEASE_CHECKLIST.md`, and
> `SPRINT4_RELEASE_READINESS.md`. Some early roadmap examples below still
> describe the original vertical-crop plan and are retained as history, not as
> the active product contract.

---

## **PART 1: SUMMARY — Apa Saja yang Sudah Dikerjakan**

### **A. Planning & Documentation (100% DONE)**

#### **Phase 1: Product Definition ✅**
- ✅ **PRD (Product Requirements Document)** — scope, features, user story, risks
- ✅ **TRD (Technical Requirements Document)** — tech stack, batasan, timeline

#### **Phase 2: System Design ✅**
- ✅ **ARCHITECTURE.md** — high-level diagram, DB schema, API contract, processing pipeline
- ✅ **SYSTEM_OVERVIEW.md** — complete system documentation
- ✅ **Database schema** — Job table, Clip table, relationships, indexes
- ✅ **API contract** — 10+ endpoints specified (request/response format)
- ✅ **Processing pipeline design** — 7 stages defined, input/output clear

#### **Phase 3: Deployment & Integration Planning ✅**
- ✅ **BACKEND_SETUP.md** — installation guide, configuration, troubleshooting
- ✅ **FRONTEND_INTEGRATION.md** — API client, hooks, components, state management
- ✅ **docker-compose.yml** — orchestration file (backend + Ollama)

---

### **B. Backend Implementation (95% DONE)**

#### **Infrastructure ✅**
| File | Status | Notes |
|---|---|---|
| `app/main.py` | ✅ | FastAPI setup + lifespan + CORS + error handlers |
| `app/config.py` | ✅ | Centralized settings (env-based) |
| `app/database.py` | ✅ | SQLAlchemy engine + SessionLocal + init_db() |
| `app/models.py` | ✅ | ORM models (Job, Clip) with relationships |
| `app/schemas.py` | ✅ | Pydantic request/response schemas |

#### **Processing Pipeline (7 stages) ✅**
| Stage | File | Status | Details |
|---|---|---|---|
| 1 | `audio_extract.py` | ✅ | Extract WAV 16kHz mono via ffmpeg |
| 2 | `transcribe.py` | ✅ | Faster Whisper lokal (model lazy-loaded) |
| 3 | `highlight_detect.py` | ✅ | Rule-based scoring (audio energy + text cues) |
| 4 | `clip_cut.py` | ✅ | Cut video segment via ffmpeg |
| 5 | `smart_crop.py` | ✅ | MediaPipe face detection + 9:16 crop |
| 6 | `subtitle_burn.py` | ✅ | SRT generation + ffmpeg subtitle overlay |
| 7 | `metadata_gen.py` | ✅ | Ollama API call (title/caption/hashtags) |

#### **Service Layer ✅**
| Component | File | Status | Details |
|---|---|---|---|
| Job Queue | `services/job_queue.py` | ✅ | In-process asyncio.Queue + worker loop |
| Job Orchestrator | `services/job_service.py` | ✅ | Coordinate stages, error handling, DB updates |

#### **API Routes ✅**
| Route Group | File | Status | Endpoints |
|---|---|---|---|
| Videos | `api/routes/videos.py` | ✅ | POST /upload, POST /youtube |
| Jobs | `api/routes/jobs.py` | ✅ | GET list, GET {id}, POST {id}/cancel |
| Clips | `api/routes/clips.py` | ✅ | GET, PATCH, DELETE, GET /file, GET /preview |

#### **Configuration ✅**
| File | Status | Purpose |
|---|---|---|
| `requirements.txt` | ✅ | Python dependencies (FastAPI, librosa, opencv, etc) |
| `Dockerfile` | ✅ | Multi-stage build image |
| `.env.example` | ✅ | Configuration template |

---

### **C. Deployment Setup (95% DONE)**

| Component | Status | Notes |
|---|---|---|
| **docker-compose.yml** | ✅ | Backend + Ollama orchestration |
| **Health checks** | ✅ | Liveness probe di Dockerfile |
| **Volume persistence** | ✅ | Database, uploads, clips, models |
| **Network setup** | ✅ | Backend ↔ Ollama via docker network |

---

### **D. Frontend Specification (100% DONE, Code Template Provided)**

| Component | Status | Details |
|---|---|---|
| **API Client** (`lib/api.ts`) | ✅ Template | All endpoints wrapped, error handling |
| **Hooks** (`hooks/useJobStatus.ts`) | ✅ Template | Polling logic, refetch interval |
| **State Management** (`store/video.ts`) | ✅ Template | Zustand store (UI state + server state) |
| **Components** | ✅ Template | VideoUpload, JobStatus, ClipCard, ClipList |
| **Types** (`types/api.ts`) | ✅ Template | TypeScript interfaces matching backend |

---

### **E. Documentation (100% COMPLETE)**

| Document | Purpose |
|---|---|
| **ARCHITECTURE.md** | System design, DB schema, API contract |
| **BACKEND_SETUP.md** | Installation, configuration, troubleshooting |
| **FRONTEND_INTEGRATION.md** | API client, hooks, complete component examples |
| **SYSTEM_OVERVIEW.md** | Full system walkthrough (end-to-end) |
| **BACKEND_DEPLOYMENT_FRONTEND_SUMMARY.md** | Executive summary |

---

### **Summary Table: Completion Status**

| Area | Progress | Status |
|---|---|---|
| **Planning** | 100% | ✅ Complete |
| **Backend Implementation** | 95% | ✅ Functional, needs testing |
| **Deployment** | 95% | ✅ Ready, needs verification |
| **Frontend** | 0% | ⏳ Template provided, needs implementation |
| **Documentation** | 100% | ✅ Complete |
| **Testing** | 0% | ⏳ Not started |
| **Optimization** | 0% | ⏳ After MVP working |

---

## **PART 2: EXECUTION ROADMAP — Langkah Berikutnya**

### **Sprint 1: Backend Verification & Setup (Week 1)**

**Goal:** Verify backend berjalan, semua pipeline stage testing, Ollama integration confirm.

#### **Task 1.1: Local Setup & Validation** (2-3 jam)
```bash
# 1. Verify docker & docker-compose installed
docker --version
docker-compose --version

# 2. Start backend
cd /path/to/video-assistant
docker-compose up -d

# 3. Verify services running
docker-compose ps
docker logs clipgen-backend
docker logs clipgen-ollama

# 4. Health checks
curl http://localhost:8000/health
curl http://localhost:11434/api/tags

# 5. Check Swagger UI
http://localhost:8000/docs
```

**Deliverable:** Backend running, health check passing, Swagger UI accessible.

---

#### **Task 1.2: Test Each Pipeline Stage Individually** (4-5 jam)

**Create test script: `backend/test_pipeline.py`**

```python
"""Manual test untuk verify setiap stage berjalan."""

import asyncio
from pathlib import Path
from app.core.pipeline import (
    audio_extract, transcribe, highlight_detect, 
    clip_cut, smart_crop, subtitle_burn, metadata_gen
)
from app.config import settings

async def test_pipeline():
    # Gunakan test video (cari video ~30 detik, simpan di backend/test_video.mp4)
    test_video = Path("test_video.mp4")
    
    if not test_video.exists():
        print("❌ test_video.mp4 tidak ada. Download atau buat video test 30 detik.")
        return
    
    print("🎥 Testing pipeline dengan test_video.mp4...")
    
    # Stage 1: Extract audio
    print("\n[1/7] Testing audio extraction...")
    audio_path = audio_extract.extract_audio(test_video, settings.temp_dir)
    print(f"✅ Audio extracted: {audio_path.name}")
    
    # Stage 2: Transcribe
    print("\n[2/7] Testing transcription...")
    segments = transcribe.transcribe(audio_path)
    print(f"✅ Transcribed {len(segments)} segments")
    for seg in segments[:3]:
        print(f"   {seg.start:.1f}s - {seg.end:.1f}s: {seg.text[:50]}...")
    
    # Stage 3: Detect highlights
    print("\n[3/7] Testing highlight detection...")
    duration = segments[-1].end if segments else 30.0
    highlights = highlight_detect.detect_highlights(segments, audio_path, duration)
    print(f"✅ Detected {len(highlights)} highlights")
    for h in highlights:
        print(f"   {h.start:.1f}s - {h.end:.1f}s (score={h.score:.2f})")
    
    if not highlights:
        print("⚠️  No highlights detected. Tune thresholds di config.py")
        return
    
    # Stage 4-6: Cut, crop, burn subtitles (sample first highlight only)
    highlight = highlights[0]
    clip_id = "test-clip"
    
    print("\n[4/7] Testing clip cutting...")
    raw_clip = clip_cut.cut_clip(test_video, highlight.start, highlight.end, settings.clips_dir, clip_id)
    print(f"✅ Clip cut: {raw_clip.name}")
    
    print("\n[5/7] Testing smart crop...")
    cropped_clip = smart_crop.smart_crop(raw_clip, settings.clips_dir, clip_id)
    print(f"✅ Clip cropped: {cropped_clip.name}")
    
    print("\n[6/7] Testing subtitle burn...")
    final_clip = subtitle_burn.burn_subtitles(cropped_clip, segments, clip_id, settings.clips_dir)
    print(f"✅ Subtitles burned: {final_clip.name}")
    
    # Stage 7: Generate metadata
    print("\n[7/7] Testing metadata generation...")
    clip_text = " ".join(s.text for s in segments if s.start >= highlight.start and s.end <= highlight.end)
    metadata = metadata_gen.generate_metadata(clip_text)
    print(f"✅ Metadata generated")
    print(f"   Title: {metadata['title']}")
    print(f"   Caption: {metadata['caption'][:60]}...")
    print(f"   Hashtags: {metadata['hashtags']}")
    
    print("\n✅ All pipeline stages working!")
    print(f"\n📹 Test clip: {final_clip}")
    print("   Play with: ffplay " + str(final_clip))

if __name__ == "__main__":
    asyncio.run(test_pipeline())
```

**Run:**
```bash
cd backend
python test_pipeline.py
```

**Expected output:**
- ✅ All 7 stages complete
- Final video file created di `storage/clips/`
- Metadata generated successfully

**Troubleshooting checklist:**
- ❌ Whisper model download failed? Check internet, RAM (model ~500MB-5GB tergantung size)
- ❌ Ollama connection failed? `docker logs clipgen-ollama`, verify port 11434 accessible
- ❌ FFmpeg error? Verify ffmpeg installed: `ffmpeg -version`
- ❌ MediaPipe import error? `pip install mediapipe` (mungkin belum di requirements.txt)

---

#### **Task 1.3: Test API Endpoints** (2-3 jam)

**Create test script: `backend/test_api.py`**

```python
"""Test API endpoints tanpa frontend."""

import requests
import json
from pathlib import Path
import time

BASE_URL = "http://localhost:8000"
TEST_VIDEO = Path("test_video.mp4")

def test_upload_endpoint():
    """Test POST /api/videos/upload"""
    print("\n[TEST] POST /api/videos/upload")
    
    with open(TEST_VIDEO, "rb") as f:
        files = {"file": f}
        response = requests.post(f"{BASE_URL}/api/videos/upload", files=files)
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code} {response.text}")
        return None
    
    data = response.json()
    job_id = data["job_id"]
    print(f"✅ Upload success, job_id={job_id}")
    return job_id

def test_job_status(job_id):
    """Test GET /api/jobs/{id}"""
    print(f"\n[TEST] GET /api/jobs/{job_id}")
    
    response = requests.get(f"{BASE_URL}/api/jobs/{job_id}")
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return
    
    job = response.json()
    print(f"✅ Status: {job['status']}, Progress: {job['progress']}%")
    return job

def test_polling_until_done(job_id, max_wait=3600):
    """Poll job status sampai done atau failed"""
    print(f"\n[TEST] Polling job {job_id} until done (max {max_wait}s)...")
    
    start = time.time()
    while time.time() - start < max_wait:
        job = test_job_status(job_id)
        
        if job["status"] in ["done", "failed"]:
            print(f"\n✅ Job finished with status: {job['status']}")
            if job["error_message"]:
                print(f"   Error: {job['error_message']}")
            return job
        
        print(f"   Waiting... (elapsed: {int(time.time()-start)}s)")
        time.sleep(5)  # poll every 5 seconds untuk testing
    
    print("❌ Timeout waiting for job")
    return None

def test_clips_endpoint(job_id):
    """Test GET /api/clips/job/{job_id}"""
    print(f"\n[TEST] GET /api/clips/job/{job_id}")
    
    response = requests.get(f"{BASE_URL}/api/clips/job/{job_id}")
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return []
    
    clips = response.json()
    print(f"✅ Found {len(clips)} clips")
    for clip in clips:
        print(f"   - {clip['id']}: {clip.get('title', 'No title')} ({clip['status']})")
    return clips

def test_download_endpoint(clip_id):
    """Test GET /api/clips/{id}/file"""
    print(f"\n[TEST] GET /api/clips/{clip_id}/file")
    
    response = requests.get(f"{BASE_URL}/api/clips/{clip_id}/file", stream=True)
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return
    
    # Save to file
    output = Path(f"downloaded_{clip_id}.mp4")
    with open(output, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    size_mb = output.stat().st_size / (1024*1024)
    print(f"✅ Downloaded: {output.name} ({size_mb:.1f}MB)")

def main():
    print("🧪 ClipGen API Integration Test")
    print(f"   Base URL: {BASE_URL}")
    print(f"   Test video: {TEST_VIDEO}")
    
    if not TEST_VIDEO.exists():
        print(f"❌ {TEST_VIDEO} tidak ada. Persiapkan test video dulu.")
        return
    
    # Test upload
    job_id = test_upload_endpoint()
    if not job_id:
        return
    
    # Poll until done
    job = test_polling_until_done(job_id)
    if not job or job["status"] != "done":
        return
    
    # Test clips
    clips = test_clips_endpoint(job_id)
    if clips:
        # Test download first clip
        test_download_endpoint(clips[0]["id"])
    
    print("\n✅ All API tests passed!")

if __name__ == "__main__":
    main()
```

**Run:**
```bash
cd backend
python test_api.py
```

**Expected output:**
- ✅ Upload success
- ✅ Job polling shows progress 0→100%
- ✅ Clips found and ready
- ✅ Download successful

**This validates backend is fully functional before moving to frontend.**

---

#### **Task 1.4: Setup Issue Logging & Monitoring** (1 jam)

**Add to `backend/app/main.py`:**
```python
# Logging setup
from loguru import logger

# Redirect logs ke file untuk debugging
logger.add(
    "backend/logs/clipgen.log",
    rotation="500 MB",
    retention="7 days",
    level="INFO"
)

# Saat startup, log versions
logger.info(f"ClipGen backend v0.1.0 started")
logger.info(f"Whisper model: {settings.whisper_model_size}")
logger.info(f"Ollama URL: {settings.ollama_base_url}")
```

**Create `backend/logs/` directory** untuk store logs.

**Deliverable:** Backend logging di file, dapat dianalisis kalau ada error.

---

### **Sprint 2: Frontend Implementation (Week 2-3)**

**Goal:** Build working frontend, integrate dengan backend, end-to-end testing.

#### **Task 2.1: Setup Next.js Project** (1 jam)

```bash
cd /path/to/video-assistant

# Create Next.js project dengan template
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --app \
  --eslint \
  --no-git

cd frontend

# Install additional dependencies
npm install \
  @tanstack/react-query \
  zustand \
  react-hook-form \
  zod \
  @hookform/resolvers \
  @radix-ui/react-dialog \
  @radix-ui/react-progress \
  clsx \
  tailwind-merge

# Setup environment
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

**Deliverable:** Fresh Next.js project dengan semua dependencies installed.

---

#### **Task 2.2: Implement API Client & Hooks** (2-3 jam)

Copy dari `FRONTEND_INTEGRATION.md`:

**`frontend/src/lib/api.ts`** — all fetch calls wrapped
**`frontend/src/hooks/useJobStatus.ts`** — polling hook
**`frontend/src/hooks/useClips.ts`** — clips fetching hook
**`frontend/src/store/video.ts`** — Zustand store
**`frontend/src/types/api.ts`** — TypeScript interfaces

**Verify:**
```bash
npm run build  # check TypeScript errors
```

---

#### **Task 2.3: Implement Core Components** (4-5 jam)

**Component hierarchy:**

```
app/
├── page.tsx (dashboard)
│   └── JobList (list past jobs)
│
├── upload/
│   └── page.tsx
│       └── VideoUploadForm
│           ├── File input
│           └── YouTube URL input
│
└── jobs/[id]/
    └── page.tsx
        ├── JobProgressBar
        │   └─ GET /api/jobs/{id} polling
        │
        └─ ClipsList (when status === done)
            └─ ClipCard[] (per clip)
                ├─ Video preview
                ├─ MetadataEditor
                └─ Download button
```

**Step-by-step implementation:**

**1. VideoUploadForm.tsx**
```tsx
// Handle file upload + YouTube URL
// Call api.uploadVideo() or api.youtubeUrl()
// Redirect to job page
```

**2. JobProgressBar.tsx**
```tsx
// useJobStatus() hook untuk polling
// Display progress bar + status text
// Handle error display
```

**3. ClipCard.tsx**
```tsx
// Video preview (<video> tag)
// Metadata display/edit (form)
// Download button
// Delete button
```

**Testing:**
```bash
npm run dev
# Open http://localhost:3000
# Try upload → should see job page
```

---

#### **Task 2.4: Integration Testing** (3-4 jam)

**Scenario 1: Upload file & polling**
- Upload test video
- Watch progress bar update
- Wait until status === done
- Verify clips appear

**Scenario 2: Edit metadata**
- Click "Edit" on clip card
- Change title/caption
- Click "Save"
- Verify changes persisted (refresh page)

**Scenario 3: Download**
- Click "Download" button
- Verify MP4 file downloaded
- Play in player to verify video works

**Scenario 4: Multiple jobs**
- Upload 2-3 videos
- Navigate between jobs
- Verify history preserved

**Document any bugs found** → create issue tracker (GitHub issues atau Trello).

---

#### **Task 2.5: Error Handling & Edge Cases** (2-3 jam)

**Add handling untuk:**
- File upload too large → show error message
- Network error during polling → retry logic
- Job failed mid-process → display error from backend
- Clip generation failed → show fallback (clip record dengan status=failed)
- Empty transcript → skip subtitle burn gracefully
- Metadata generation timeout → use default values

---

### **Sprint 3: Testing & Optimization (Week 4)**

**Goal:** Comprehensive testing, performance tuning, bug fixes.

#### **Task 3.1: Unit Tests (Backend)** (4-5 jam)

**Test structure:**
```
backend/tests/
├── test_pipeline.py
│   ├─ test_highlight_detection()
│   └─ test_smart_crop_fallback()
├── test_job_service.py
│   └─ test_job_processing_flow()
└── test_api.py
    └─ test_upload_endpoint()
```

**Example test:**
```python
import pytest
from app.core.pipeline.highlight_detect import detect_highlights
from app.core.pipeline.transcribe import Segment

def test_highlight_detection_empty_segments():
    """Edge case: no speech in video"""
    segments = []
    highlights = detect_highlights(segments, audio_path, duration=60.0)
    assert len(highlights) == 0

def test_highlight_detection_full_laughter():
    """Normal case: full video is laughter"""
    segments = [
        Segment(0, 10, "haha haha haha"),
        Segment(10, 20, "wkwk wkwk"),
    ]
    highlights = detect_highlights(segments, audio_path, duration=20.0)
    assert len(highlights) > 0
```

**Run tests:**
```bash
cd backend
pytest tests/ -v
```

---

#### **Task 3.2: Load Testing** (2-3 jam)

**Test dengan video berbagai durasi:**

| Video Length | Expected Time | Priority |
|---|---|---|
| 5 menit | ~2-3 menit | P0 |
| 30 menit | ~5-8 menit | P0 |
| 1 jam | ~15-20 menit | P1 |

**Optimization opportunities:**
- Whisper model size (tiny vs base vs small) — trade-off speed vs accuracy
- Highlight detection window size — smaller window = faster
- Clip generation: generate all 5 in parallel? (currently sequential)

---

#### **Task 3.3: Database Cleanup & Maintenance** (1-2 jam)

**Add maintenance tasks:**

```python
# backend/services/maintenance.py

async def cleanup_temp_files(older_than_hours=24):
    """Delete temp files older than N hours"""
    from datetime import datetime, timedelta
    
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    for f in settings.temp_dir.glob("*"):
        if f.stat().st_mtime < cutoff.timestamp():
            f.unlink()

async def cleanup_old_uploads(older_than_days=7):
    """Delete uploaded videos older than N days (setelah job selesai)"""
    from datetime import datetime, timedelta
    from app.models import Job
    
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    old_jobs = db.query(Job).filter(Job.updated_at < cutoff).all()
    for job in old_jobs:
        # Delete file + DB record
```

**Schedule dengan APScheduler (optional):**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(cleanup_temp_files, "interval", hours=6)
scheduler.add_job(cleanup_old_uploads, "interval", days=1)
scheduler.start()
```

---

### **Sprint 4: Documentation & Release (Week 5)**

**Goal:** Complete documentation, prepare for deployment/sharing.

#### **Task 4.1: Complete README** (1-2 jam)

**Root level `README.md`:**
```markdown
# ClipGen — Personal AI Video Assistant

## Quick Start

### Option 1: Docker Compose (Recommended)
\`\`\`bash
docker-compose up -d
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
\`\`\`

### Option 2: Manual Setup
[Link ke BACKEND_SETUP.md + FRONTEND_SETUP.md]

## Features
- Video upload + YouTube URL support
- Auto-detect highlight moments
- Smart crop to 9:16 vertical
- Auto-generate subtitles
- AI-powered metadata (title, caption, hashtags)

## Architecture
[Link ke ARCHITECTURE.md]

## API Documentation
http://localhost:8000/docs (Swagger UI)

## Contributing
[Development guide]

## License
MIT
```

---

#### **Task 4.2: Create Deployment Guide** (2 jam)

**`DEPLOYMENT.md`:**
- Production setup (cloud provider: Render, Railway, Heroku, GCP)
- Environment variables untuk production
- Database migration strategy (SQLite → Postgres)
- Model caching strategy (Whisper, Ollama model pre-download)
- Monitoring & logging di production

---

#### **Task 4.3: Create Video Tutorial / Walkthrough** (optional, 2-3 jam)

- Screen recording: upload video → watch processing → download clips
- Show each feature
- Common troubleshooting

---

## **PART 3: CRITICAL POINTS TO WATCH OUT FOR**

### **🚨 Critical Issues — Perhatian Khusus**

#### **1. Memory Management (Whisper Model Loading)**
**Issue:** Loading Whisper model ke memory bisa consume 500MB-5GB tergantung model size.

**Solution:**
- Gunakan `faster-whisper` bukan `openai-whisper` (lebih ringan)
- Model size di-tune via config: `WHISPER_MODEL_SIZE=tiny|base|small`
- Model di-load sekali jadi singleton → reuse lintas job
- Monitor memory: `docker stats clipgen-backend`

**Watch for:**
- ❌ OOM (Out of Memory) error saat transcribe
- ❌ Slow processing karena model load ulang

---

#### **2. Ollama Connection Timeout**
**Issue:** Ollama server startup lambat, atau metadata generation timeout.

**Solution:**
- Set `OLLAMA_BASE_URL` dengan benar di environment
- Add retry logic di `metadata_gen.py`:
  ```python
  max_retries = 3
  for attempt in range(max_retries):
      try:
          response = requests.post(..., timeout=60)
          return response
      except requests.Timeout:
          if attempt < max_retries - 1:
              time.sleep(2)
          else:
              raise
  ```
- Fallback ke default metadata kalau Ollama fail

**Watch for:**
- ❌ Metadata generation hang (timeout > 60 detik)
- ❌ "Cannot connect to Ollama" error

---

#### **3. Face Detection Failure (MediaPipe)**
**Issue:** Anime/cartoon/multiple faces → face detection jadi salah.

**Solution:**
- Add fallback ke center-crop statis (sudah implemented di `smart_crop.py`)
- Test dengan berbagai video type: real-talk, anime, gaming, music video
- Tune MediaPipe confidence threshold kalau perlu

**Watch for:**
- ❌ Crop terlalu close ke face (cut off head)
- ❌ Crop terlalu jauh (wasted space)

---

#### **4. Subtitle Timing Issues**
**Issue:** Subtitle tidak sync dengan audio, atau terpotong.

**Solution:**
- Verify transcript segment timestamps akurat dari Whisper
- Test dengan video berbagai bahasa (Bahasa Indonesia, English, dll)
- Add margin ke subtitle timing:
  ```python
  adj_start = max(0, seg.start - 0.5)  # 0.5s margin
  adj_end = min(clip_duration, seg.end + 0.5)
  ```

**Watch for:**
- ❌ Subtitle muncul terlalu cepat/lambat
- ❌ Subtitle text terpotong di akhir

---

#### **5. YouTube Download Intermittent Failures**
**Issue:** `yt-dlp` bisa fail jika YouTube ubah struktur atau blocking.

**Solution:**
- Keep `yt-dlp` updated: `pip install --upgrade yt-dlp`
- Add retry logic:
  ```python
  max_retries = 3
  for attempt in range(max_retries):
      result = subprocess.run(cmd, capture_output=True)
      if result.returncode == 0:
          return
      time.sleep(2)
  ```
- Provide fallback: "YouTube download failed, upload file directly instead"

**Watch for:**
- ❌ Random 403/429 errors dari YouTube
- ❌ yt-dlp version conflict dengan ffmpeg

---

#### **6. Database Locking (SQLite)**
**Issue:** Multiple backend instances competing untuk write ke SQLite.

**Solution:**
- **NEVER run multiple backend instances** (design single-writer)
- Kalau perlu scale, migrate ke Postgres + Redis (lihat v2.0 improvements)
- Keep transaction scope small:
  ```python
  # ❌ BAD: long transaction
  job = get_job()
  do_long_processing()  # 10 menit
  update_job()
  
  # ✅ GOOD: short transactions
  update_job_status("processing", 10)
  do_long_processing()  # 10 menit (no transaction)
  update_job_status("done", 100)
  ```

**Watch for:**
- ❌ "database is locked" error di logs
- ❌ Jobs stuck di "processing" status

---

#### **7. File System Space**
**Issue:** Storage/uploads/, storage/clips/ bisa jadi penuh.

**Solution:**
- Monitor disk space: `df -h`
- Add cleanup task (lihat Task 3.3 maintenance)
- Config max upload size: `MAX_UPLOAD_SIZE_MB=2048`
- Archive old jobs: move to external storage kalau perlu

**Watch for:**
- ❌ "No space left on device" error
- ❌ Uploads ditolak karena over limit

---

#### **8. CORS Issues (Development → Production)**
**Issue:** Frontend di domain lain cannot call backend API.

**Solution:**
- Dev: CORS already configured untuk localhost:3000
- Production: Update CORS di `app/main.py`:
  ```python
  allow_origins=["https://yourdomain.com"]  # bukan http://localhost
  ```

**Watch for:**
- ❌ "Access-Control-Allow-Origin" header error di browser
- ❌ API call blocked oleh CORS

---

### **⚡ Performance Watch Points**

| Bottleneck | Current | Target | Action |
|---|---|---|---|
| **Whisper transcription** | 5-10min untuk 1hr video | 2-3min | Use `tiny` model, parallel processing (v2.0) |
| **Highlight detection** | ~1min untuk 1hr video | <30s | Optimize window size, caching |
| **Face detection** | ~2-3s per clip | <1s | MediaPipe optimization, skip if not needed |
| **Metadata generation** | 5-10s per clip | <5s | Parallel Ollama calls (v2.0) |
| **Total end-to-end** | ~30min untuk 1hr + 5clips | 15-20min | Parallel stages (v2.0) |

---

### **🔐 Security Watch Points**

| Risk | Mitigation | Status |
|---|---|---|
| **File upload security** | Validate file type (ffprobe), size limit, scan for malware | ⏳ Add file type validation |
| **Command injection** | Use subprocess with list args, not shell=True | ✅ Already doing |
| **Path traversal** | Validate file paths, no `..` in filenames | ✅ Already doing |
| **Rate limiting** | Add rate limiter di FastAPI (optional) | ⏳ v2.0 |
| **Auth** | Not needed for personal project | N/A |

---

## **PART 4: FUTURE IMPROVEMENTS — Roadmap v2.0, v3.0**

### **v1.0 (Current — MVP)**

✅ Single video upload/YouTube URL
✅ Rule-based highlight detection
✅ Auto-crop + subtitle + metadata
✅ 3-5 clips per video
✅ Local processing (offline capable)

---

### **v1.5 — Quality & Stability Improvements**

**Priority: High**

1. **Unit Tests** (backend)
   - Coverage: 70%+ untuk critical paths (pipeline stages)
   - Estimate: 1 sprint

2. **Error Recovery**
   - Resume failed jobs (checkpoint system)
   - Graceful degradation (skip subtitle kalau fail, tapi lanjut export)
   - Estimate: 2-3 days

3. **Performance Optimization**
   - Parallel stage processing (cut + crop + subtitle simultaneously)
   - Model caching improvements
   - Estimate: 3-4 days

4. **UI/UX Polish**
   - Better error messages
   - Progress visualization (not just percentage)
   - Dark mode (optional)
   - Estimate: 2-3 days

**Timeline:** 2-3 weeks (after v1.0 stabilization)

---

### **v2.0 — Scaling & Advanced Features**

**Priority: Medium-High**

1. **Multi-User Support** (breaking change)
   - Add authentication (JWT or OAuth)
   - User isolation (user_id foreign key di jobs/clips)
   - Estimate: 2 weeks

2. **Distributed Processing** (infrastructure upgrade)
   - Replace in-process queue → Celery + Redis
   - Horizontal scaling (multiple worker instances)
   - Estimate: 2 weeks

3. **Database Upgrade**
   - SQLite → PostgreSQL + connection pooling
   - Data migration strategy
   - Estimate: 1 week

4. **Advanced Highlight Detection**
   - Machine learning model (fine-tune on "viral" videos)
   - Combine heuristik + ML (ensemble)
   - Estimate: 3-4 weeks

5. **Batch Processing**
   - Process multiple videos in queue
   - Scheduled jobs (process every night)
   - Estimate: 1 week

6. **Export Enhancements**
   - Direct upload to TikTok/Instagram (API integration)
   - Batch export
   - Custom watermark
   - Estimate: 2 weeks

**Timeline:** 8-10 weeks (Q2-Q3)

---

### **v3.0 — Intelligence & Customization**

**Priority: Medium**

1. **Customizable Highlight Detection**
   - UI slider untuk tune sensitivity
   - A/B test different algorithms
   - User feedback loop (rate detected clips)
   - Estimate: 2 weeks

2. **Smart Metadata Generation**
   - Multiple language support (not just Indonesian)
   - Trendy hashtag suggestion (analyze trending topics)
   - Emoji support di title/caption
   - Estimate: 1-2 weeks

3. **Content Analytics**
   - Track which clips perform well (via TikTok API integration)
   - Suggest improvements
   - Learning system (improve detection based on feedback)
   - Estimate: 3 weeks

4. **Advanced Video Editing**
   - Manual clip editing UI (trim, adjust)
   - Custom transitions/effects
   - Music/background sound overlay
   - Estimate: 4 weeks

5. **Mobile App** (React Native or Flutter)
   - Native iOS/Android app
   - Upload directly from phone
   - Offline support for Whisper (large binary)
   - Estimate: 6-8 weeks

**Timeline:** 12-16 weeks (Q3-Q4)

---

### **v4.0 — Enterprise & Monetization (Future)**

**Priority: Low (future vision)**

1. **SaaS Platform**
   - Subscription model (free tier, pro, enterprise)
   - Usage-based billing (videos processed, storage)
   - Multi-team support
   - Estimate: 8 weeks

2. **API for Third-Parties**
   - REST API untuk programmatic access
   - Rate limiting, API keys
   - Estimate: 2 weeks

3. **White-Label Solution**
   - Custom branding
   - On-premise deployment
   - Estimate: 2 weeks

4. **Integration Ecosystem**
   - Zapier integration
   - Slack bot
   - Discord bot
   - Estimate: 2-3 weeks

---

### **Prioritization Matrix (Next 6 months)**

```
              EFFORT →
          Low        High
IMPACT ↑
High    v1.5       v2.0 (Distributed)
        Tests      Multi-user
        UI Polish  Database upgrade
        
Low     v3.0       v4.0 (Enterprise)
        Analytics  White-label
        Mobile     SaaS
```

**Recommended:** v1.0 → v1.5 → v2.0 (first 6 months)

---

## **PART 5: SUCCESS CRITERIA & COMPLETION CHECKLIST**

### **v1.0 MVP — Completion Checklist**

**Backend:**
- ✅ All 7 pipeline stages implemented
- ✅ API endpoints working
- ✅ Database schema finalized
- ⏳ Error handling per stage (graceful degradation)
- ⏳ Logging setup
- ⏳ Basic unit tests

**Frontend:**
- ⏳ Upload form (file + YouTube)
- ⏳ Job status polling
- ⏳ Clip preview + download
- ⏳ Metadata editor
- ⏳ Error messages

**Deployment:**
- ✅ docker-compose.yml ready
- ⏳ Health checks verified
- ⏳ Documentation complete

**Testing:**
- ⏳ End-to-end test (upload → download)
- ⏳ Edge case testing (large file, no speech, anime, etc)

**Documentation:**
- ✅ ARCHITECTURE.md
- ✅ BACKEND_SETUP.md
- ✅ FRONTEND_INTEGRATION.md
- ⏳ README.md (root level)
- ⏳ DEPLOYMENT.md

---

### **Success Metrics**

| Metric | Target | How to Measure |
|---|---|---|
| **Video Processing Time** | <30min untuk 1hr video | Time job dari upload → done |
| **Highlight Accuracy** | >70% user satisfaction | Manual review clips |
| **Subtitle Quality** | >90% word accuracy | Spot check transcripts |
| **System Reliability** | 99% uptime | Monitor logs, 0 crashes |
| **API Response Time** | <200ms untuk GET request | Monitor via curl, profiling |

---

## **PART 6: FINAL EXECUTION STEPS**

### **Week-by-Week Roadmap**

```
WEEK 1: Backend Verification
  ├─ Task 1.1: Docker setup + health checks
  ├─ Task 1.2: Pipeline stage testing
  ├─ Task 1.3: API endpoint testing
  └─ Task 1.4: Logging setup

WEEK 2: Frontend Implementation (Part 1)
  ├─ Task 2.1: Next.js setup
  ├─ Task 2.2: API client + hooks
  └─ Task 2.3: Core components (50% done)

WEEK 3: Frontend Implementation (Part 2) + Integration
  ├─ Task 2.3: Complete components
  ├─ Task 2.4: E2E integration testing
  └─ Task 2.5: Error handling

WEEK 4: Testing & Bug Fixes
  ├─ Task 3.1: Unit tests
  ├─ Task 3.2: Load testing
  └─ Task 3.3: Database maintenance

WEEK 5: Documentation & Release
  ├─ Task 4.1: README
  ├─ Task 4.2: Deployment guide
  └─ Task 4.3: Final testing
```

**Total timeline: 5 weeks (MVP v1.0 production-ready)**

---

## **PART 7: HOW TO PROCEED FROM HERE**

### **Immediate Next Steps (Start Monday)**

1. **Read this document fully** (1-2 hours) ✅
2. **Run Sprint 1 — Backend Verification** (1-2 days)
   - Docker setup
   - Pipeline testing
   - API testing
3. **Fix any issues found** (1-2 days)
4. **Proceed to Sprint 2 — Frontend** (if backend passing)

---

### **Tools & Resources to Setup**

| Tool | Purpose | Setup Time |
|---|---|---|
| **Docker Desktop** | Container runtime | 15 min |
| **VS Code** | Development IDE | 15 min |
| **Postman/Insomnia** | API testing | 10 min |
| **Git + GitHub** | Version control | 15 min |
| **SQLite Browser** | Database inspection | 5 min |

---

### **Key Files to Keep Bookmarked**

```
📚 Documentation
├── ARCHITECTURE.md              ← System design reference
├── BACKEND_SETUP.md             ← How to run backend
├── FRONTEND_INTEGRATION.md      ← API client + component code
├── SYSTEM_OVERVIEW.md           ← Full system walkthrough
├── This file                    ← Execution roadmap

📝 Configuration
├── backend/.env.example         ← Environment template
├── backend/requirements.txt      ← Python dependencies
├── docker-compose.yml           ← Docker orchestration
└── backend/Dockerfile           ← Backend image

💻 Code (Backend)
├── backend/app/main.py          ← FastAPI app
├── backend/app/services/        ← Job queue + orchestrator
├── backend/app/core/pipeline/   ← Processing stages
└── backend/app/api/routes/      ← API endpoints

🎨 Code (Frontend)
├── frontend/src/lib/api.ts      ← API client template
├── frontend/src/hooks/          ← Custom hooks template
├── frontend/src/store/          ← State management template
└── frontend/src/components/     ← Component templates
```

---

**Good luck! 🚀**

Ini adalah project yang sudah well-designed, well-documented, dan ready untuk execution. Focus pada:
1. Verify backend works (Sprint 1)
2. Build frontend (Sprint 2)
3. Test thoroughly (Sprint 3)
4. Deploy & celebrate (Sprint 4)

Kalau ada pertanyaan during execution, refer ke dokumentasi atau trace through kode yang sudah ada.

---

**Last updated: January 2025**
**Status: MVP v1.0 ready for Sprint 1 execution**
