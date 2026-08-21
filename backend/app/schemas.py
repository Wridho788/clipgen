"""
Pydantic schemas — kontrak data masuk/keluar API.
Ini yang jadi acuan manual untuk Zod schema di frontend (lihat
lib/schemas.ts) karena versi minimal ini belum pakai OpenAPI codegen.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import settings


class JobProcessingOptions(BaseModel):
    """Per-job processing switches tanpa mengubah default server."""

    min_clip_seconds: float = Field(ge=5, le=120)
    max_clip_seconds: float = Field(ge=5, le=120)
    # Zero means adaptive planning from source duration; a positive number is
    # an explicit user target, never a hidden fixed batch size.
    clip_count: int = Field(default=0, ge=0, le=12)
    metadata_language: Literal["id", "en"] = "id"
    processing_mode: Literal["automatic", "manual"] = "manual"
    crop_vertical: bool = False
    generate_highlights: bool = True
    generate_metadata: bool = True
    generate_subtitles: bool = False
    # Contextual cues supplement audio energy so candidates can surface a
    # joke, emotional beat, reveal, or payoff rather than only loud moments.
    context_aware: bool = True
    output_preset: Literal["original", "tiktok", "reels", "youtube_shorts", "square", "landscape"] = "original"
    visual_style: Literal["clean", "blur", "crop", "zoom", "split"] = "clean"
    subtitle_style: Literal["standard", "karaoke"] = "standard"
    hook_text: Optional[str] = Field(default=None, max_length=120)
    # Kept for backwards-compatible requests; runtime always resolves this
    # automatically and exposes the actual CPU/GPU label to the user.
    render_acceleration: Literal["auto", "cpu", "gpu"] = "auto"

    @model_validator(mode="after")
    def validate_processing_options(self):
        if self.min_clip_seconds > self.max_clip_seconds:
            raise ValueError("min_clip_seconds tidak boleh lebih besar dari max_clip_seconds")
        if self.processing_mode == "automatic":
            self.crop_vertical = False
            # Highlight analysis is an explicit automatic-mode choice.  It can
            # be skipped for a faster default-window clip while metadata and
            # subtitles remain independently selectable.
        if self.crop_vertical and self.output_preset == "original":
            # Keep legacy requests working while routing them through the
            # newer social renderer.
            self.output_preset = "tiktok"
            if self.visual_style == "clean":
                self.visual_style = "crop"
        elif self.output_preset == "original":
            # There is no fixed social canvas to apply blur/split to. Preserve
            # the source aspect cleanly until a platform preset is selected.
            self.visual_style = "clean"
        if self.hook_text:
            self.hook_text = self.hook_text.strip() or None
        self.render_acceleration = "auto"
        return self


def default_processing_options() -> JobProcessingOptions:
    """Build defaults at request time so environment overrides tetap berlaku."""
    return JobProcessingOptions(
        min_clip_seconds=settings.highlight_min_clip_seconds,
        max_clip_seconds=settings.highlight_max_clip_seconds,
        clip_count=settings.highlight_top_n,
        metadata_language=settings.metadata_default_language,
        processing_mode="manual",
        crop_vertical=False,
        generate_highlights=True,
        generate_metadata=True,
        generate_subtitles=False,
        context_aware=True,
        output_preset="original",
        visual_style="clean",
        subtitle_style="standard",
        hook_text=None,
        render_acceleration=settings.render_acceleration,
    )


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    estimated_processing_seconds: float = 0
    stage_estimates: dict[str, float] = Field(default_factory=dict)


class ProcessingEstimateResponse(BaseModel):
    duration_seconds: float
    source_type: Literal["upload", "youtube_url"]
    stage_estimates: dict[str, float]
    estimated_processing_seconds: float


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_type: str
    source_name: Optional[str] = None
    source_duration_seconds: Optional[float] = None
    source_size_bytes: Optional[int] = None
    processing_options: Optional[str] = None
    parent_job_id: Optional[str] = None
    retry_count: int = 0
    queue_position: Optional[int] = None
    status: str
    progress: int
    error_message: Optional[str] = None
    warning_message: Optional[str] = None
    stage_metrics_json: Optional[str] = None
    stage_estimates_json: Optional[str] = None
    automatic_summary_json: Optional[str] = None
    stage_metrics: dict[str, float] = Field(default_factory=dict)
    stage_estimates: dict[str, float] = Field(default_factory=dict)
    automatic_summary: dict[str, object] = Field(default_factory=dict)
    estimated_total_seconds: float = 0
    current_stage_eta_seconds: float = 0
    current_stage_elapsed_seconds: float = 0
    overall_eta_seconds: float = 0
    runtime: dict[str, object] = Field(default_factory=dict)
    estimated_completion_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class JobRetryRequest(BaseModel):
    """Optional processing options saat menjalankan ulang sebuah job terminal."""

    processing_options: Optional[JobProcessingOptions] = None


class ClipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    start_time: float
    end_time: float
    highlight_score: float
    file_path: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None  # JSON string, di-parse di frontend
    distribution: Optional[dict[str, object]] = None
    status: str
    created_at: datetime


class ClipUpdateRequest(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[list[str]] = None


class ClipTrimRequest(BaseModel):
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_time - self.start_time < 5:
            raise ValueError("Durasi klip minimal 5 detik")
        if self.end_time - self.start_time > 120:
            raise ValueError("Durasi klip maksimal 120 detik")
        return self


class ClipFeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    reason: Optional[str] = Field(default=None, max_length=160)


class ClipFeedbackResponse(BaseModel):
    rating: Literal[-1, 1] | None = None
    reason: Optional[str] = None
    positive_count: int = 0
    negative_count: int = 0


class StorageClearRequest(BaseModel):
    """Explicit destructive-storage request from the local operations UI."""

    mode: Literal["recycle", "permanent"] = "recycle"
    confirmation: Optional[str] = None

    @model_validator(mode="after")
    def require_permanent_confirmation(self):
        if self.mode == "permanent" and self.confirmation != "DELETE_PERMANENTLY":
            raise ValueError("Konfirmasi hapus permanen tidak valid")
        return self


class AuthRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class AuthUserResponse(BaseModel):
    id: str
    username: str
    display_name: str


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: AuthUserResponse
