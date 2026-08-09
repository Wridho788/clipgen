import {
  ClipResponse,
  ClipUpdateRequest,
  JobProcessingOptions,
  JobCreateResponse,
  JobResponse,
  JobStatus,
  ProcessingEstimateResponse,
  ReleaseInfoResponse,
  SystemMetricsResponse,
} from "@/types/api";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    let message = response.statusText;

    try {
      if (contentType.includes("application/json")) {
        const data = await response.json();
        const detail = data?.detail;
        if (typeof detail === "string") {
          message = detail;
        } else if (Array.isArray(detail)) {
          message = detail.map((item) => item?.msg || JSON.stringify(item)).join(", ");
        } else {
          message = data?.message || JSON.stringify(data);
        }
      } else {
        message = await response.text();
      }
    } catch {
      message = response.statusText;
    }

    throw new Error(message || `API error ${response.status}`);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  // --- Videos ---
  uploadVideo: async (
    file: File,
    options?: Partial<JobProcessingOptions>,
    onProgress?: (progress: UploadProgress) => void,
  ): Promise<JobCreateResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    appendProcessingOptions(formData, options);
    return uploadWithProgress(`${API_BASE_URL}/api/videos/upload`, formData, onProgress);
  },

  youtubeUrl: async (
    url: string,
    options?: Partial<JobProcessingOptions>,
  ): Promise<JobCreateResponse> => {
    const formData = new FormData();
    formData.append("url", url);
    appendProcessingOptions(formData, options);
    const response = await fetch(`${API_BASE_URL}/api/videos/youtube`, {
      method: "POST",
      body: formData,
    });
    return handleResponse(response);
  },

  getProcessingEstimate: async (
    durationSeconds: number,
    sourceType: "upload" | "youtube_url",
    options?: Partial<JobProcessingOptions>,
  ): Promise<ProcessingEstimateResponse> => {
    const params = new URLSearchParams({
      duration_seconds: String(durationSeconds),
      source_type: sourceType,
    });
    if (options?.min_clip_seconds !== undefined) params.set("min_clip_seconds", String(options.min_clip_seconds));
    if (options?.max_clip_seconds !== undefined) params.set("max_clip_seconds", String(options.max_clip_seconds));
    if (options?.clip_count !== undefined) params.set("clip_count", String(options.clip_count));
    if (options?.metadata_language) params.set("metadata_language", options.metadata_language);
    if (options?.processing_mode) params.set("processing_mode", options.processing_mode);
    if (options?.crop_vertical !== undefined) params.set("crop_vertical", String(options.crop_vertical));
    if (options?.generate_highlights !== undefined) params.set("generate_highlights", String(options.generate_highlights));
    if (options?.generate_metadata !== undefined) params.set("generate_metadata", String(options.generate_metadata));
    if (options?.generate_subtitles !== undefined) params.set("generate_subtitles", String(options.generate_subtitles));
    const response = await fetch(`${API_BASE_URL}/api/videos/estimate?${params.toString()}`);
    return handleResponse(response);
  },

  // --- Jobs ---
  getJobStatus: async (jobId: string): Promise<JobResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
    return handleResponse(response);
  },

  listJobs: async (status?: JobStatus): Promise<JobResponse[]> => {
    const url = status
      ? `${API_BASE_URL}/api/jobs?status=${encodeURIComponent(status)}`
      : `${API_BASE_URL}/api/jobs`;
    const response = await fetch(url);
    return handleResponse(response);
  },

  cancelJob: async (jobId: string): Promise<{ status: string; job_id: string }> => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/cancel`, {
      method: "POST",
    });
    return handleResponse(response);
  },

  retryJob: async (
    jobId: string,
    processingOptions?: JobProcessingOptions,
  ): Promise<JobCreateResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(processingOptions ? { processing_options: processingOptions } : {}),
    });
    return handleResponse(response);
  },

  // --- Clips ---
  getClipsByJob: async (jobId: string): Promise<ClipResponse[]> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/job/${jobId}`);
    return handleResponse(response);
  },

  getClip: async (clipId: string): Promise<ClipResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}`);
    return handleResponse(response);
  },

  updateClip: async (clipId: string, data: ClipUpdateRequest): Promise<ClipResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  regenerateClipMetadata: async (clipId: string): Promise<ClipResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}/regenerate-metadata`, {
      method: "POST",
    });
    return handleResponse(response);
  },

  deleteClip: async (clipId: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}`, {
      method: "DELETE",
    });
    await handleResponse(response);
  },

  getClipPreviewUrl: (clipId: string): string =>
    `${API_BASE_URL}/api/clips/${clipId}/preview`,

  getClipDownloadUrl: (clipId: string): string =>
    `${API_BASE_URL}/api/clips/${clipId}/file`,

  getJobArchiveUrl: (jobId: string): string =>
    `${API_BASE_URL}/api/clips/job/${jobId}/archive`,

  getSystemMetrics: async (): Promise<SystemMetricsResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/system/metrics`);
    return handleResponse(response);
  },

  getReleaseInfo: async (): Promise<ReleaseInfoResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/system/release`);
    return handleResponse(response);
  },
};

function appendProcessingOptions(formData: FormData, options?: Partial<JobProcessingOptions>) {
  if (options?.min_clip_seconds !== undefined) {
    formData.append("min_clip_seconds", String(options.min_clip_seconds));
  }
  if (options?.max_clip_seconds !== undefined) {
    formData.append("max_clip_seconds", String(options.max_clip_seconds));
  }
  if (options?.clip_count !== undefined) {
    formData.append("clip_count", String(options.clip_count));
  }
  if (options?.metadata_language) {
    formData.append("metadata_language", options.metadata_language);
  }
  if (options?.processing_mode) {
    formData.append("processing_mode", options.processing_mode);
  }
  if (options?.crop_vertical !== undefined) {
    formData.append("crop_vertical", String(options.crop_vertical));
  }
  if (options?.generate_highlights !== undefined) {
    formData.append("generate_highlights", String(options.generate_highlights));
  }
  if (options?.generate_metadata !== undefined) {
    formData.append("generate_metadata", String(options.generate_metadata));
  }
  if (options?.generate_subtitles !== undefined) {
    formData.append("generate_subtitles", String(options.generate_subtitles));
  }
}

function uploadWithProgress(
  url: string,
  formData: FormData,
  onProgress?: (progress: UploadProgress) => void,
): Promise<JobCreateResponse> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.responseType = "text";

    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress?.({
        loaded: event.loaded,
        total: event.total,
        percent: Math.min(100, Math.round((event.loaded / event.total) * 100)),
      });
    };
    request.onerror = () => reject(new Error("Koneksi upload terputus."));
    request.onabort = () => reject(new Error("Upload dibatalkan."));
    request.onload = () => {
      const body = request.responseText || "";
      if (request.status >= 200 && request.status < 300) {
        try {
          resolve(JSON.parse(body) as JobCreateResponse);
        } catch {
          reject(new Error("Respons upload tidak valid."));
        }
        return;
      }
      reject(new Error(getErrorMessage(body, request.statusText, request.status)));
    };
    request.send(formData);
  });
}

function getErrorMessage(body: string, statusText: string, status: number): string {
  try {
    const data = JSON.parse(body);
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((item: { msg?: string }) => item?.msg || JSON.stringify(item))
        .join(", ");
    }
    if (typeof data?.message === "string") return data.message;
  } catch {
    // The fallback below covers plain-text proxy and server errors.
  }
  return body || statusText || `API error ${status}`;
}
