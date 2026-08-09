# Frontend Integration Guide

## Overview

Frontend (Next.js) berkomunikasi dengan backend (FastAPI) via REST JSON API.

```
Next.js (port 3000)
       │
       ├─→ POST /api/videos/upload (multipart FormData)
       ├─→ GET /api/jobs/{id} (polling tiap 2 detik)
       ├─→ GET /api/clips/job/{id} (list clips)
       ├─→ GET /api/clips/{id}/preview (stream video)
       └─→ PATCH /api/clips/{id} (edit metadata)
       │
Backend API (port 8000)
```

---

## API Client Setup (lib/api.ts)

```typescript
// lib/api.ts

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  // --- Videos ---
  uploadVideo: async (file: File): Promise<{ job_id: string }> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE_URL}/api/videos/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  youtubeUrl: async (url: string): Promise<{ job_id: string }> => {
    const formData = new FormData();
    formData.append("url", url);

    const response = await fetch(`${API_BASE_URL}/api/videos/youtube`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  // --- Jobs ---
  getJobStatus: async (jobId: string): Promise<JobResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
    if (!response.ok) throw new Error("Job not found");
    return response.json();
  },

  listJobs: async (): Promise<JobResponse[]> => {
    const response = await fetch(`${API_BASE_URL}/api/jobs`);
    if (!response.ok) throw new Error("Failed to list jobs");
    return response.json();
  },

  cancelJob: async (jobId: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/cancel`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("Failed to cancel job");
  },

  // --- Clips ---
  getClipsByJob: async (jobId: string): Promise<ClipResponse[]> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/job/${jobId}`);
    if (!response.ok) throw new Error("Failed to get clips");
    return response.json();
  },

  getClip: async (clipId: string): Promise<ClipResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}`);
    if (!response.ok) throw new Error("Clip not found");
    return response.json();
  },

  updateClip: async (
    clipId: string,
    data: { title?: string; caption?: string; hashtags?: string[] }
  ): Promise<ClipResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("Failed to update clip");
    return response.json();
  },

  deleteClip: async (clipId: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error("Failed to delete clip");
  },

  // --- File streaming ---
  getClipPreviewUrl: (clipId: string): string => {
    return `${API_BASE_URL}/api/clips/${clipId}/preview`;
  },

  getClipDownloadUrl: (clipId: string): string => {
    return `${API_BASE_URL}/api/clips/${clipId}/file`;
  },
};
```

---

## Polling Strategy (hooks/useJobStatus.ts)

Job processing async dan butuh polling untuk dapatkan status progress.

```typescript
// hooks/useJobStatus.ts

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { JobResponse } from "@/types/api";

export const useJobStatus = (jobId: string, enabled: boolean = true) => {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !jobId) return;

    let isMounted = true;
    let pollInterval: NodeJS.Timeout;

    const poll = async () => {
      try {
        const data = await api.getJobStatus(jobId);
        if (isMounted) {
          setJob(data);
          setLoading(false);
          setError(null);

          // Stop polling kalau job selesai atau gagal
          if (data.status === "done" || data.status === "failed") {
            if (pollInterval) clearInterval(pollInterval);
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Unknown error");
          setLoading(false);
        }
      }
    };

    // Poll immediately, then every 2 seconds
    poll();
    pollInterval = setInterval(poll, 2000);

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [jobId, enabled]);

  return { job, loading, error };
};
```

**Usage di component:**

```typescript
// app/jobs/[id]/page.tsx

"use client";

import { useJobStatus } from "@/hooks/useJobStatus";
import { useClips } from "@/hooks/useClips";

export default function JobPage({ params }: { params: { id: string } }) {
  const { job, loading, error } = useJobStatus(params.id);
  const { clips } = useClips(job?.id || "");

  if (loading) return <div>Loading job status...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!job) return <div>Job not found</div>;

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded">
        <h2 className="font-bold">Job {job.id}</h2>
        <p>Status: {job.status}</p>
        <div className="w-full bg-gray-300 rounded h-2 mt-2">
          <div
            className="bg-blue-600 h-2 rounded transition-all"
            style={{ width: `${job.progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-600 mt-2">{job.progress}% complete</p>
      </div>

      {job.status === "done" && clips.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-bold">Generated Clips</h3>
          {clips.map((clip) => (
            <ClipCard key={clip.id} clip={clip} />
          ))}
        </div>
      )}

      {job.status === "failed" && (
        <div className="bg-red-50 p-4 rounded">
          <p className="text-red-700">{job.error_message}</p>
        </div>
      )}
    </div>
  );
}
```

---

## Video Upload with Progress (components/VideoUpload.tsx)

```typescript
// components/VideoUpload.tsx

"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

export function VideoUpload() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      // Note: fetch API tidak support progress events untuk upload.
      // Untuk production, pakai axios atau XMLHttpRequest untuk onUploadProgress.
      // Untuk MVP ini, cukup show spinner.
      
      const result = await api.uploadVideo(file);
      
      // Redirect ke job page
      router.push(`/jobs/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    }
  };

  return (
    <div className="border-2 border-dashed rounded-lg p-8 text-center">
      <input
        type="file"
        accept="video/*"
        onChange={handleFileSelect}
        disabled={uploading}
        className="hidden"
        id="file-input"
      />
      <label htmlFor="file-input" className="cursor-pointer">
        <p className="font-semibold">
          {uploading ? "Uploading..." : "Click to select video"}
        </p>
        <p className="text-sm text-gray-500">
          or drag and drop (max 2GB)
        </p>
      </label>
      
      {uploading && (
        <div className="mt-4">
          <div className="w-48 h-2 bg-gray-200 rounded mx-auto">
            <div className="h-2 bg-blue-600 rounded animate-pulse" />
          </div>
        </div>
      )}
      
      {error && <p className="text-red-600 mt-4">{error}</p>}
    </div>
  );
}
```

---

## Clip Preview & Editor (components/ClipCard.tsx)

```typescript
// components/ClipCard.tsx

"use client";

import { useState } from "react";
import { ClipResponse } from "@/types/api";
import { api } from "@/lib/api";

export function ClipCard({ clip }: { clip: ClipResponse }) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(clip.title || "");
  const [caption, setCaption] = useState(clip.caption || "");
  const [hashtags, setHashtags] = useState(
    typeof clip.hashtags === "string" ? JSON.parse(clip.hashtags) : []
  );

  const handleSave = async () => {
    await api.updateClip(clip.id, {
      title,
      caption,
      hashtags,
    });
    setIsEditing(false);
  };

  return (
    <div className="border rounded-lg p-4 bg-white">
      {/* Video Preview */}
      <video
        src={api.getClipPreviewUrl(clip.id)}
        controls
        className="w-full rounded mb-4"
      />

      {/* Metadata Display/Edit */}
      {isEditing ? (
        <div className="space-y-4">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title"
            className="w-full border rounded px-3 py-2"
          />
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Caption"
            className="w-full border rounded px-3 py-2 h-20"
          />
          <input
            type="text"
            value={hashtags.join(" ")}
            onChange={(e) =>
              setHashtags(e.target.value.split(" ").filter(Boolean))
            }
            placeholder="Hashtags (space-separated)"
            className="w-full border rounded px-3 py-2"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-green-600 text-white rounded"
            >
              Save
            </button>
            <button
              onClick={() => setIsEditing(false)}
              className="px-4 py-2 bg-gray-300 rounded"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <h3 className="font-bold text-lg">{title}</h3>
          <p className="text-gray-700">{caption}</p>
          <div className="flex flex-wrap gap-2">
            {hashtags.map((tag) => (
              <span key={tag} className="text-blue-600">
                #{tag}
              </span>
            ))}
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => setIsEditing(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded"
            >
              Edit
            </button>
            <a
              href={api.getClipDownloadUrl(clip.id)}
              download={`${title}.mp4`}
              className="px-4 py-2 bg-green-600 text-white rounded"
            >
              Download
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## Types (types/api.ts)

```typescript
// types/api.ts

export interface JobResponse {
  id: string;
  source_type: "upload" | "youtube_url";
  status: "pending" | "extracting" | "transcribing" | "detecting" | "cutting" | "cropping" | "subtitling" | "generating_metadata" | "done" | "failed" | "cancelled";
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClipResponse {
  id: string;
  job_id: string;
  start_time: number;
  end_time: number;
  highlight_score: number;
  file_path: string | null;
  title: string | null;
  caption: string | null;
  hashtags: string | null; // JSON string, parse ke array
  status: "processing" | "ready" | "failed";
  created_at: string;
}
```

---

## Environment Variables (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## CORS & Deployment Notes

### Local Development
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- CORS sudah di-setup di FastAPI (lihat `main.py`)

### Production
Kalau deploy ke domain beda, update CORS di `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # bukan localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Next Steps

1. **Setup backend** (lihat `BACKEND_SETUP.md`)
2. **Setup frontend** (Next.js project + copy files di atas)
3. **Integration testing** (manual test upload → polling → download)
4. **Deploy** (lihat root `README.md`)
