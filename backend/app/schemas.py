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
    clip_count: int = Field(ge=1, le=10)
    metadata_language: Literal["id", "en"] = "id"
    processing_mode: Literal["automatic", "manual"] = "manual"
    crop_vertical: bool = False
    generate_highlights: bool = True
    generate_metadata: bool = True
    generate_subtitles: bool = False

    @model_validator(mode="after")
    def validate_processing_options(self):
        if self.min_clip_seconds > self.max_clip_seconds:
            raise ValueError("min_clip_seconds tidak boleh lebih besar dari max_clip_seconds")
        if self.processing_mode == "automatic":
            self.crop_vertical = False
            self.generate_highlights = True
            self.generate_metadata = True
            self.generate_subtitles = False
            # Automatic mode should provide a useful set of candidate clips,
            # not the single deterministic clip used when detection is off.
            self.clip_count = max(3, self.clip_count)
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
    status: str
    progress: int
    error_message: Optional[str] = None
    warning_message: Optional[str] = None
    stage_metrics_json: Optional[str] = None
    stage_estimates_json: Optional[str] = None
    stage_metrics: dict[str, float] = Field(default_factory=dict)
    stage_estimates: dict[str, float] = Field(default_factory=dict)
    estimated_total_seconds: float = 0
    current_stage_eta_seconds: float = 0
    overall_eta_seconds: float = 0
    estimated_completion_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
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
    status: str
    created_at: datetime


class ClipUpdateRequest(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[list[str]] = None
