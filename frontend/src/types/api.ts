// Types — harus sinkron manual dengan backend/app/schemas.py dan
// backend/app/core/edit_model.py (belum pakai OpenAPI codegen).

export type JobStatus =
  | "pending"
  | "downloading"
  | "extracting"
  | "transcribing"
  | "cutting"
  | "cropping"
  | "generating_metadata"
  | "done"
  | "failed"
  | "cancelled";

export type ClipStatus = "processing" | "ready" | "failed";

export type CampaignPlatform = "tiktok" | "instagram_reels" | "youtube" | "facebook";

export interface CampaignBrief {
  id: string;
  name: string;
  description: string;
  platforms: CampaignPlatform[];
  min_clip_seconds: number;
  max_clip_seconds: number;
  hook_required: boolean;
  hook_max_seconds: number;
  preferred_hook_types: string[];
  required_visuals: string[];
  required_phrases: string[];
  prohibited_terms: string[];
  hashtags: string[];
  mentions: string[];
  cta: string | null;
  title_style: "curiosity_truthful" | "direct" | "brand_safe";
  source_only: boolean;
  organic_only: boolean;
  avoid_misleading_edits: boolean;
  positive_brand_tone: boolean;
  allow_voiceover: boolean;
  retention_lock: boolean;
}

// --- Campaigns (backend/app/schemas.py: CampaignConfigData & friends) ---

export interface CampaignConfigData {
  schema_version: 1;
  objective: string;
  brief: string;
  target_audience: string;
  platforms: CampaignPlatform[];
  /** Machine-checkable rules the pipeline and compliance check understand. */
  rules: CampaignBrief;
  soft_preferences: string[];
  reward_details: string | null;
  unresolved_items: string[];
}

export interface CampaignSummary {
  id: string;
  name: string;
  type: "reward" | "custom";
  source: "manual_import" | "user_created";
  source_name: string | null;
  source_url: string | null;
  status: "active" | "archived";
  latest_version: number;
  confirmed: boolean;
  created_at: string;
  updated_at: string;
}

export interface CampaignConfiguration {
  campaign_id: string;
  version: number;
  config: CampaignConfigData;
  raw_source_text: string | null;
  user_confirmed_at: string | null;
  created_at: string;
}

export interface CampaignDetail extends CampaignSummary {
  configuration: CampaignConfiguration;
}

export interface CampaignCreateRequest {
  name: string;
  type?: "reward" | "custom";
  source?: "manual_import" | "user_created";
  source_name?: string | null;
  source_url?: string | null;
  config: CampaignConfigData;
  raw_source_text?: string | null;
  confirmed: boolean;
}

export interface CampaignUpdateRequest {
  name?: string;
  config: CampaignConfigData;
  raw_source_text?: string | null;
  confirmed: boolean;
}

export type ExtractedFieldStatus = "found" | "needs_review" | "not_provided";

export interface ExtractedField {
  status: ExtractedFieldStatus;
  value: number | string | string[] | null;
  evidence: string[];
  note: string | null;
}

export type CampaignImportFieldName =
  | "min_clip_seconds"
  | "max_clip_seconds"
  | "hashtags"
  | "mentions"
  | "platforms"
  | "source_urls"
  | "prohibited_terms"
  | "cta"
  | "dates";

export interface CampaignImportDraft {
  raw_source_text: string;
  truncated: boolean;
  fields: Record<CampaignImportFieldName, ExtractedField>;
  unresolved_items: string[];
  warnings: string[];
}

export interface JobProcessingOptions {
  min_clip_seconds: number;
  max_clip_seconds: number;
  clip_count: number;
  metadata_language: "id" | "en";
  /** Spoken language for Whisper; "auto" lets Whisper detect it. */
  transcript_language?: "auto" | "id" | "en";
  processing_mode: "automatic" | "manual";
  crop_vertical: boolean;
  generate_metadata: boolean;
  burn_captions?: boolean;
  output_preset: "original" | "tiktok" | "reels" | "youtube_shorts" | "square" | "landscape";
  visual_style: "clean" | "blur" | "crop" | "zoom" | "split";
  campaign_brief?: CampaignBrief | null;
  /** Saved campaign; the backend pins its version and snapshots the brief into the job. */
  campaign_id?: string | null;
  campaign_configuration_version?: number | null;
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

export interface YoutubePreflightResponse {
  can_start: boolean;
  status: "ready" | "cookies_missing" | "cooldown";
  message: string;
  retry_after_seconds: number;
  cookies_ready: boolean;
}

export interface CampaignCompliance {
  status: "pass" | "review_required" | "blocked";
  score: number;
  checks: Array<{ key: string; label: string; status: "pass" | "review_required" | "blocked"; detail: string }>;
}

export interface JobResponse {
  id: string;
  source_type: "upload" | "youtube_url";
  source_name: string | null;
  source_duration_seconds: number | null;
  source_size_bytes: number | null;
  processing_options: string | null;
  parent_job_id: string | null;
  campaign_id?: string | null;
  campaign_configuration_version?: number | null;
  retry_count: number;
  queue_position: number | null;
  status: JobStatus;
  progress: number;
  error_message: string | null;
  error_code?: string | null;
  warning_message: string | null;
  stage_metrics_json: string | null;
  stage_estimates_json: string | null;
  automatic_summary_json: string | null;
  stage_metrics: Record<string, number>;
  stage_estimates: Record<string, number>;
  automatic_summary: Record<string, unknown>;
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

export type ReviewStatus = "suggested" | "accepted" | "rejected" | "edited" | "exported";

export type RejectionReason =
  | "context_missing"
  | "weak_moment"
  | "bad_boundaries"
  | "transcript_error"
  | "repeated_content"
  | "poor_crop"
  | "other";

export type OutputPreset = JobProcessingOptions["output_preset"];
export type VisualStyle = JobProcessingOptions["visual_style"];

export interface CaptionStyle {
  font_size: number;
  text_color: string;
  background: "none" | "outline" | "box";
  background_color: string;
  position_y: number;
  max_chars_per_line: number;
  bold: boolean;
}

export interface CaptionCue {
  id: string;
  start_ms: number;
  end_ms: number;
  text: string;
  original_text?: string | null;
}

/** Canonical edit document shared by the preview and the FFmpeg export. */
export interface ClipEdit {
  schema_version: number;
  trim_start_ms: number;
  trim_end_ms: number;
  output_preset: OutputPreset;
  visual_style: VisualStyle;
  framing: { focus_x: number; focus_y: number };
  captions: { enabled: boolean; style: CaptionStyle; cues: CaptionCue[] };
  audio: { enabled: boolean; normalize: boolean };
  watermark_enabled: boolean;
}

export interface CandidateInfo {
  algorithm_version: string;
  rank?: number;
  total?: number;
  score_meaning: string;
  signals: Record<string, number>;
  explanation: string[];
}

export interface RenderReport {
  revision: number;
  rendered_at: string;
  render_seconds: number;
  encoder: string;
  captions_rendered: number;
  validation: {
    ok: boolean;
    checks: Record<string, boolean>;
    problems: string[];
    width: number | null;
    height: number | null;
    duration_seconds: number | null;
    has_audio: boolean;
    size_bytes: number;
  };
}

export interface ClipResponse {
  id: string;
  job_id: string;
  start_time: number;
  end_time: number;
  suggested_start_time?: number | null;
  suggested_end_time?: number | null;
  file_path: string | null;
  title: string | null;
  caption: string | null;
  hashtags: string | null; // JSON-encoded string, parse dengan JSON.parse
  distribution?: DistributionPack | null;
  status: ClipStatus;
  review_status?: ReviewStatus;
  review_reason?: RejectionReason | null;
  position?: number | null;
  candidate?: CandidateInfo | null;
  edit?: ClipEdit | null;
  edit_revision?: number;
  rendered_revision?: number | null;
  render_stale?: boolean;
  render_error_code?: string | null;
  render_error_message?: string | null;
  render_report?: RenderReport | null;
  exported_at?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface DistributionPack {
  source_name: string | null;
  hashtag_source: "youtube_source_tags+clip_metadata" | "clip_metadata_fallback";
  campaign?: {
    id: string;
    name: string;
    cta: string | null;
    mentions: string[];
    organic_only: boolean;
    retention_lock: boolean;
  } | null;
  compliance?: CampaignCompliance | null;
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
    vertical_crop: boolean;
    youtube_manual_options: boolean;
    youtube_automatic_multi_clip: boolean;
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
