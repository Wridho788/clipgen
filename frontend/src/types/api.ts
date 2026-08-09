// Types — harus sinkron manual dengan backend/app/schemas.py
// (versi minimal ini belum pakai OpenAPI codegen, lihat ARCHITECTURE.md)

export type JobStatus =
  | "pending"
  | "downloading"
  | "extracting"
  | "transcribing"
  | "detecting"
  | "cutting"
  | "cropping"
  | "subtitling"
  | "generating_metadata"
  | "done"
  | "failed"
  | "cancelled";

export type ClipStatus = "processing" | "ready" | "failed";

export interface JobProcessingOptions {
  min_clip_seconds: number;
  max_clip_seconds: number;
  clip_count: number;
  metadata_language: "id" | "en";
  processing_mode: "automatic" | "manual";
  crop_vertical: boolean;
  generate_highlights: boolean;
  generate_metadata: boolean;
  generate_subtitles: boolean;
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
  estimated_processing_seconds: number;
  stage_estimates: Record<string, number>;
}

export interface ProcessingEstimateResponse {
  duration_seconds: number;
  source_type: "upload" | "youtube_url";
  stage_estimates: Record<string, number>;
  estimated_processing_seconds: number;
}

export interface JobResponse {
  id: string;
  source_type: "upload" | "youtube_url";
  source_name: string | null;
  source_duration_seconds: number | null;
  source_size_bytes: number | null;
  processing_options: string | null;
  parent_job_id: string | null;
  retry_count: number;
  status: JobStatus;
  progress: number;
  error_message: string | null;
  warning_message: string | null;
  stage_metrics_json: string | null;
  stage_estimates_json: string | null;
  stage_metrics: Record<string, number>;
  stage_estimates: Record<string, number>;
  estimated_total_seconds: number;
  current_stage_eta_seconds: number;
  overall_eta_seconds: number;
  estimated_completion_at: string | null;
  processing_started_at: string | null;
  completed_at: string | null;
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
  hashtags: string | null; // JSON-encoded string, parse dengan JSON.parse
  status: ClipStatus;
  created_at: string;
}

export interface ClipUpdateRequest {
  title?: string;
  caption?: string;
  hashtags?: string[];
}

export interface SystemMetricsResponse {
  queue: {
    queue_size: number;
    worker_running: boolean;
    worker_started_at: string | null;
    current_job_id: string | null;
    current_job_started_at: string | null;
    processed_jobs: number;
    failed_jobs: number;
  };
  jobs: Record<string, number>;
  clips: Record<string, number>;
  storage_bytes: {
    uploads: number;
    clips: number;
    temp: number;
  };
}

export interface ReleaseInfoResponse {
  name: string;
  version: string;
  release_channel: string;
  environment: string;
  limits: {
    max_upload_size_mb: number;
    youtube_download_timeout_seconds: number;
    temp_file_retention_hours: number;
  };
  defaults: {
    metadata_language: "id" | "en";
    whisper_model_size: string;
    whisper_device: string;
  };
  features: {
    local_upload: boolean;
    youtube_url: boolean;
    upload_subtitles: boolean;
    youtube_subtitles: boolean;
    vertical_crop: boolean;
    youtube_manual_options: boolean;
    metadata_language_selector: boolean;
    playwright_e2e: boolean;
  };
  known_risks: string[];
}

export function parseHashtags(hashtags: string | null): string[] {
  if (!hashtags) return [];
  try {
    const parsed = JSON.parse(hashtags);
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
  } catch {
    return [];
  }
}
