import {
  AuthConfigResponse,
  AuthSessionResponse,
  AuthUser,
  ClipFeedbackResponse,
  ClipResponse,
  ClipUpdateRequest,
  JobProcessingOptions,
  JobCreateResponse,
  JobResponse,
  JobStatus,
  ProcessingEstimateResponse,
  ReleaseInfoResponse,
  SystemMetricsResponse,
  StorageClearMode,
  StorageClearResponse,
} from "@/types/api";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ACCESS_TOKEN_KEY = "clipgen-access-token";

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

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

function withAccessToken(url: string): string {
  const token = getAccessToken();
  if (!token) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}access_token=${encodeURIComponent(token)}`;
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
    const response = await apiFetch(`${API_BASE_URL}/api/videos/youtube`, {
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
    if (options?.context_aware !== undefined) params.set("context_aware", String(options.context_aware));
    if (options?.output_preset) params.set("output_preset", options.output_preset);
    if (options?.visual_style) params.set("visual_style", options.visual_style);
    if (options?.subtitle_style) params.set("subtitle_style", options.subtitle_style);
    if (options?.hook_text) params.set("hook_text", options.hook_text);
    if (options?.render_acceleration) params.set("render_acceleration", options.render_acceleration);
    const response = await apiFetch(`${API_BASE_URL}/api/videos/estimate?${params.toString()}`);
    return handleResponse(response);
  },

  // --- Jobs ---
  getJobStatus: async (jobId: string): Promise<JobResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/jobs/${jobId}`);
    return handleResponse(response);
  },

  listJobs: async (status?: JobStatus): Promise<JobResponse[]> => {
    const url = status
      ? `${API_BASE_URL}/api/jobs?status=${encodeURIComponent(status)}`
      : `${API_BASE_URL}/api/jobs`;
    const response = await apiFetch(url);
    return handleResponse(response);
  },

  cancelJob: async (jobId: string): Promise<{ status: string; job_id: string }> => {
    const response = await apiFetch(`${API_BASE_URL}/api/jobs/${jobId}/cancel`, {
      method: "POST",
    });
    return handleResponse(response);
  },

  retryJob: async (
    jobId: string,
    processingOptions?: JobProcessingOptions,
  ): Promise<JobCreateResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/jobs/${jobId}/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(processingOptions ? { processing_options: processingOptions } : {}),
    });
    return handleResponse(response);
  },

  // --- Clips ---
  getClipsByJob: async (jobId: string): Promise<ClipResponse[]> => {
    const response = await apiFetch(`${API_BASE_URL}/api/clips/job/${jobId}`);
    return handleResponse(response);
  },

  getClip: async (clipId: string): Promise<ClipResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/clips/${clipId}`);
    return handleResponse(response);
  },

  updateClip: async (clipId: string, data: ClipUpdateRequest): Promise<ClipResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/clips/${clipId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  regenerateClipMetadata: async (clipId: string): Promise<ClipResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/clips/${clipId}/regenerate-metadata`, {
      method: "POST",
    });
    return handleResponse(response);
  },

  deleteClip: async (clipId: string): Promise<void> => {
    const response = await apiFetch(`${API_BASE_URL}/api/clips/${clipId}`, {
      method: "DELETE",
    });
    await handleResponse(response);
  },

  getClipPreviewUrl: (clipId: string): string =>
    withAccessToken(`${API_BASE_URL}/api/clips/${clipId}/preview`),

  getClipDownloadUrl: (clipId: string): string =>
    withAccessToken(`${API_BASE_URL}/api/clips/${clipId}/file`),

  getJobArchiveUrl: (jobId: string): string =>
    withAccessToken(`${API_BASE_URL}/api/clips/job/${jobId}/archive`),

  getSystemMetrics: async (): Promise<SystemMetricsResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/system/metrics`);
    return handleResponse(response);
  },

  clearStorage: async (mode: StorageClearMode): Promise<StorageClearResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/system/storage/clear`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode,
        confirmation: mode === "permanent" ? "DELETE_PERMANENTLY" : undefined,
      }),
    });
    return handleResponse(response);
  },

  getReleaseInfo: async (): Promise<ReleaseInfoResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/system/release`);
    return handleResponse(response);
  },

  getClipFeedback: async (clipId: string): Promise<ClipFeedbackResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/clips/${clipId}/feedback`);
    return handleResponse(response);
  },

  rateClip: async (
    clipId: string,
    rating: -1 | 1,
    reason?: string,
  ): Promise<ClipFeedbackResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/clips/${clipId}/feedback`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating, reason: reason || undefined }),
    });
    return handleResponse(response);
  },

  trimClip: async (clipId: string, startTime: number, endTime: number): Promise<ClipResponse> => {
    const response = await apiFetch(`${API_BASE_URL}/api/clips/${clipId}/trim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_time: startTime, end_time: endTime }),
    });
    return handleResponse(response);
  },

  getAuthConfig: async (): Promise<AuthConfigResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/auth/config`);
    return handleResponse(response);
  },

  login: async (username: string, password: string): Promise<AuthSessionResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const session = await handleResponse<AuthSessionResponse>(response);
    window.localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
    return session;
  },

  register: async (
    displayName: string,
    username: string,
    password: string,
  ): Promise<AuthSessionResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName, username, password }),
    });
    const session = await handleResponse<AuthSessionResponse>(response);
    window.localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
    return session;
  },

  getCurrentUser: async (): Promise<AuthUser> => {
    const response = await apiFetch(`${API_BASE_URL}/api/auth/me`);
    return handleResponse(response);
  },

  logout: () => {
    if (typeof window !== "undefined") window.localStorage.removeItem(ACCESS_TOKEN_KEY);
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
  if (options?.context_aware !== undefined) {
    formData.append("context_aware", String(options.context_aware));
  }
  if (options?.output_preset) formData.append("output_preset", options.output_preset);
  if (options?.visual_style) formData.append("visual_style", options.visual_style);
  if (options?.subtitle_style) formData.append("subtitle_style", options.subtitle_style);
  if (options?.hook_text) formData.append("hook_text", options.hook_text);
  if (options?.render_acceleration) formData.append("render_acceleration", options.render_acceleration);
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
    const token = getAccessToken();
    if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);

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
