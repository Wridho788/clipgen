// Types — harus sinkron manual dengan backend/app/schemas.py
// (versi minimal ini belum pakai OpenAPI codegen, lihat ARCHITECTURE.md)

export type JobStatus =
  | "pending"
  | "downloading"
  | "analyzing_intro"
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
  context_aware: boolean;
  output_preset: "original" | "tiktok" | "reels" | "youtube_shorts" | "square" | "landscape";
  visual_style: "clean" | "blur" | "crop" | "zoom" | "split";
  subtitle_style: "standard" | "karaoke";
  hook_text: string | null;
  render_acceleration: "auto";
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
  queue_position: number | null;
  status: JobStatus;
  progress: number;
  error_message: string | null;
  warning_message: string | null;
  stage_metrics_json: string | null;
  stage_estimates_json: string | null;
  automatic_summary_json: string | null;
  stage_metrics: Record<string, number>;
  stage_estimates: Record<string, number>;
  automatic_summary: Record<string, string | number | boolean>;
  estimated_total_seconds: number;
  current_stage_eta_seconds: number;
  current_stage_elapsed_seconds: number;
  overall_eta_seconds: number;
  runtime: {
    label: string;
    transcription_device: "cpu" | "cuda";
    render_device: "cpu" | "gpu";
    gpu_compatible: boolean;
  };
  estimated_completion_at: string | null;
  processing_started_at: string | null;
  heartbeat_at: string | null;
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
  distribution?: DistributionPack | null;
  status: ClipStatus;
  created_at: string;
}

export interface DistributionPack {
  source_name: string | null;
  hashtag_source: "youtube_source_tags+clip_metadata" | "clip_metadata_fallback";
  youtube: {
    title: string;
    description: string;
    tags: string[];
    hashtags: string;
    checklist: string[];
  };
  facebook: {
    caption: string;
    hashtags: string;
    checklist: string[];
  };
}

export interface ClipUpdateRequest {
  title?: string;
  caption?: string;
  hashtags?: string[];
}

export interface ClipFeedbackResponse {
  rating: -1 | 1 | null;
  reason: string | null;
  positive_count: number;
  negative_count: number;
}

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
}

export interface AuthSessionResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AuthUser;
}

export interface AuthConfigResponse {
  enabled: boolean;
  registration_enabled: boolean;
}

export interface SystemMetricsResponse {
  queue: {
    queue_size: number;
    raw_queue_size: number;
    cancelled_in_queue: number;
    worker_running: boolean;
    worker_started_at: string | null;
    current_job_id: string | null;
    current_job_started_at: string | null;
    processed_jobs: number;
    failed_jobs: number;
    skipped_cancelled_jobs: number;
  };
  jobs: Record<string, number>;
  clips: Record<string, number>;
  storage_bytes: {
    uploads: number;
    clips: number;
    temp: number;
  };
  storage_policy: {
    temp_cleanup_enabled: boolean;
    temp_file_retention_hours: number;
    upload_retention_days: number;
    clip_retention_days: number;
    permanent_asset_cleanup_enabled: boolean;
  };
  feedback: {
    positive: number;
    negative: number;
  };
}

export type StorageClearMode = "recycle" | "permanent";

export interface StorageClearResponse {
  mode: StorageClearMode;
  files_handled: number;
  bytes_moved: number;
  bytes_reclaimed: number;
  jobs_deleted: number;
  clips_deleted: number;
  recycle_path: string | null;
}

export interface ReleaseInfoResponse {
  name: string;
  version: string;
  release_channel: string;
  environment: string;
  auth: {
    enabled: boolean;
    token_ttl_hours: number;
  };
  limits: {
    max_upload_size_mb: number;
    youtube_download_timeout_seconds: number;
    temp_file_retention_hours: number;
  };
  defaults: {
    metadata_language: "id" | "en";
    whisper_model_size: string;
    whisper_device: string;
    render_acceleration: "auto";
  };
  acceleration: {
    default_mode: "auto";
    label: string;
    transcription_device: "cpu" | "cuda";
    render_device: "cpu" | "gpu";
    cuda_device_count: number;
    ffmpeg_has_nvenc_encoder: boolean;
    nvenc_runtime_usable: boolean;
    gpu_compatible: boolean;
  };
  features: {
    local_upload: boolean;
    youtube_url: boolean;
    upload_subtitles: boolean;
    youtube_subtitles: boolean;
    vertical_crop: boolean;
    youtube_manual_options: boolean;
    youtube_automatic_multi_clip: boolean;
    youtube_visual_intro_analysis: boolean;
    metadata_language_selector: boolean;
    playwright_e2e: boolean;
    clip_quality_feedback: boolean;
    local_multi_user: boolean;
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
