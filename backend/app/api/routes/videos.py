"""Video intake routes for local uploads, YouTube jobs, and ETA previews."""
import json
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_current_user
from app.core.pipeline.audio_extract import has_audio_stream
from app.database import get_db
from app.models import Job, User
from app.schemas import (
    JobCreateResponse,
    JobProcessingOptions,
    ProcessingEstimateResponse,
    default_processing_options,
)
from app.services.job_dispatcher import enqueue_job
from app.services.eta_calibration import calibrate_stage_estimates
from app.services.media_probe import probe_video
from app.services.processing_estimator import build_stage_estimates, total_estimate_seconds

router = APIRouter()


@router.get("/estimate", response_model=ProcessingEstimateResponse)
async def estimate_processing_time(
    duration_seconds: float = Query(..., gt=1, le=14_400),
    source_type: Literal["upload", "youtube_url"] = Query("upload"),
    min_clip_seconds: float | None = Query(None),
    max_clip_seconds: float | None = Query(None),
    clip_count: int | None = Query(None),
    metadata_language: Literal["id", "en"] | None = Query(None),
    processing_mode: Literal["automatic", "manual"] | None = Query(None),
    crop_vertical: bool | None = Query(None),
    generate_highlights: bool | None = Query(None),
    generate_metadata: bool | None = Query(None),
    generate_subtitles: bool | None = Query(None),
    context_aware: bool | None = Query(None),
    output_preset: Literal["original", "tiktok", "reels", "youtube_shorts", "square", "landscape"] | None = Query(None),
    visual_style: Literal["clean", "blur", "crop", "zoom", "split"] | None = Query(None),
    subtitle_style: Literal["standard", "karaoke"] | None = Query(None),
    hook_text: str | None = Query(None),
    render_acceleration: Literal["auto", "cpu", "gpu"] | None = Query(None),
):
    """Return the same conservative estimate that will be attached to a new job."""
    options = _processing_options_from_values(
        min_clip_seconds,
        max_clip_seconds,
        clip_count,
        metadata_language,
        processing_mode,
        crop_vertical,
        generate_highlights,
        generate_metadata,
        generate_subtitles,
        context_aware,
        output_preset,
        visual_style,
        subtitle_style,
        hook_text,
        render_acceleration,
    )
    stage_estimates = build_stage_estimates(duration_seconds, source_type, options)
    return ProcessingEstimateResponse(
        duration_seconds=duration_seconds,
        source_type=source_type,
        stage_estimates=stage_estimates,
        estimated_processing_seconds=total_estimate_seconds(stage_estimates),
    )


@router.post("/upload", response_model=JobCreateResponse)
async def upload_video(
    file: UploadFile = File(...),
    min_clip_seconds: float | None = Form(None),
    max_clip_seconds: float | None = Form(None),
    clip_count: int | None = Form(None),
    metadata_language: Literal["id", "en"] | None = Form(None),
    processing_mode: Literal["automatic", "manual"] | None = Form(None),
    crop_vertical: bool | None = Form(None),
    generate_highlights: bool | None = Form(None),
    generate_metadata: bool | None = Form(None),
    generate_subtitles: bool | None = Form(None),
    context_aware: bool | None = Form(None),
    output_preset: Literal["original", "tiktok", "reels", "youtube_shorts", "square", "landscape"] | None = Form(None),
    visual_style: Literal["clean", "blur", "crop", "zoom", "split"] | None = Form(None),
    subtitle_style: Literal["standard", "karaoke"] | None = Form(None),
    hook_text: str | None = Form(None),
    render_acceleration: Literal["auto", "cpu", "gpu"] | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store a local video, validate its media streams, then queue processing."""
    job_id = str(uuid.uuid4())
    file_ext = Path(file.filename).suffix if file.filename else ".mp4"
    saved_path = settings.upload_dir / f"{job_id}{file_ext}"
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024

    try:
        bytes_written = 0
        with open(saved_path, "wb") as output_file:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File terlalu besar. Max: {settings.max_upload_size_mb}MB",
                    )
                output_file.write(chunk)
    except HTTPException:
        saved_path.unlink(missing_ok=True)
        raise
    except Exception as error:
        saved_path.unlink(missing_ok=True)
        logger.error(f"File save error: {error}")
        raise HTTPException(status_code=500, detail="Gagal simpan file") from error

    video_info = probe_video(saved_path)
    if not video_info:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File bukan video valid atau corrupt")

    processing_options = _processing_options_from_values(
        min_clip_seconds,
        max_clip_seconds,
        clip_count,
        metadata_language,
        processing_mode,
        crop_vertical,
        generate_highlights,
        generate_metadata,
        generate_subtitles,
        context_aware,
        output_preset,
        visual_style,
        subtitle_style,
        hook_text,
        render_acceleration,
    )
    if (processing_options.generate_highlights or processing_options.generate_subtitles) and not has_audio_stream(saved_path):
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="Video tidak punya audio track. Upload video dengan suara/speech agar bisa diproses.",
        )

    stage_estimates, _ = calibrate_stage_estimates(
        db,
        "upload",
        build_stage_estimates(
            video_info.duration_seconds,
            "upload",
            processing_options,
        ),
    )
    job = Job(
        id=job_id,
        owner_id=current_user.id,
        source_type="upload",
        source_path=str(saved_path),
        source_name=Path(file.filename or "video").name,
        source_duration_seconds=video_info.duration_seconds,
        source_size_bytes=bytes_written,
        processing_options=processing_options.model_dump_json(),
        stage_estimates_json=json.dumps(stage_estimates),
        status="pending",
    )
    db.add(job)
    db.commit()
    logger.info(f"Job created: {job_id}, file: {saved_path.name}")

    await enqueue_job(job_id)
    return _job_create_response(job_id, "pending", stage_estimates)


@router.post("/youtube", response_model=JobCreateResponse)
async def process_youtube(
    url: str = Form(...),
    min_clip_seconds: float | None = Form(None),
    max_clip_seconds: float | None = Form(None),
    clip_count: int | None = Form(None),
    metadata_language: Literal["id", "en"] | None = Form(None),
    processing_mode: Literal["automatic", "manual"] | None = Form(None),
    crop_vertical: bool | None = Form(None),
    generate_highlights: bool | None = Form(None),
    generate_metadata: bool | None = Form(None),
    generate_subtitles: bool | None = Form(None),
    context_aware: bool | None = Form(None),
    output_preset: Literal["original", "tiktok", "reels", "youtube_shorts", "square", "landscape"] | None = Form(None),
    visual_style: Literal["clean", "blur", "crop", "zoom", "split"] | None = Form(None),
    subtitle_style: Literal["standard", "karaoke"] | None = Form(None),
    hook_text: str | None = Form(None),
    render_acceleration: Literal["auto", "cpu", "gpu"] | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue YouTube downloading in the worker so the UI gets a job immediately."""
    normalized_url = url.strip()
    if not _is_youtube_url(normalized_url):
        raise HTTPException(status_code=400, detail="URL YouTube tidak valid")

    processing_options = _processing_options_from_values(
        min_clip_seconds,
        max_clip_seconds,
        clip_count,
        metadata_language,
        processing_mode,
        crop_vertical,
        generate_highlights,
        generate_metadata,
        generate_subtitles,
        context_aware,
        output_preset,
        visual_style,
        subtitle_style,
        hook_text,
        render_acceleration,
    )
    stage_estimates, _ = calibrate_stage_estimates(
        db,
        "youtube_url",
        build_stage_estimates(None, "youtube_url", processing_options),
    )
    job = Job(
        id=str(uuid.uuid4()),
        owner_id=current_user.id,
        source_type="youtube_url",
        # The original URL is retained until the worker has a downloaded local asset.
        source_path=normalized_url,
        source_name=normalized_url,
        processing_options=processing_options.model_dump_json(),
        stage_estimates_json=json.dumps(stage_estimates),
        status="pending",
    )
    db.add(job)
    db.commit()
    logger.info(f"YouTube job queued: {job.id}")

    await enqueue_job(job.id)
    return _job_create_response(job.id, "pending", stage_estimates)


def _job_create_response(
    job_id: str,
    status: str,
    stage_estimates: dict[str, float],
) -> JobCreateResponse:
    return JobCreateResponse(
        job_id=job_id,
        status=status,
        stage_estimates=stage_estimates,
        estimated_processing_seconds=total_estimate_seconds(stage_estimates),
    )


def _is_youtube_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and (
        hostname == "youtu.be" or hostname == "youtube.com" or hostname.endswith(".youtube.com")
    )


def _processing_options_from_form(
    min_clip_seconds: float | None,
    max_clip_seconds: float | None,
    clip_count: int | None,
    metadata_language: Literal["id", "en"] | None = None,
    processing_mode: Literal["automatic", "manual"] | None = None,
    crop_vertical: bool | None = None,
    generate_highlights: bool | None = None,
    generate_metadata: bool | None = None,
    generate_subtitles: bool | None = None,
    context_aware: bool | None = None,
    output_preset: Literal["original", "tiktok", "reels", "youtube_shorts", "square", "landscape"] | None = None,
    visual_style: Literal["clean", "blur", "crop", "zoom", "split"] | None = None,
    subtitle_style: Literal["standard", "karaoke"] | None = None,
    hook_text: str | None = None,
    render_acceleration: Literal["auto", "cpu", "gpu"] | None = None,
) -> JobProcessingOptions:
    """Backward-compatible helper used by tests and multipart endpoints."""
    return _processing_options_from_values(
        min_clip_seconds,
        max_clip_seconds,
        clip_count,
        metadata_language,
        processing_mode,
        crop_vertical,
        generate_highlights,
        generate_metadata,
        generate_subtitles,
        context_aware,
        output_preset,
        visual_style,
        subtitle_style,
        hook_text,
        render_acceleration,
    )


def _processing_options_from_values(
    min_clip_seconds: float | None,
    max_clip_seconds: float | None,
    clip_count: int | None,
    metadata_language: Literal["id", "en"] | None,
    processing_mode: Literal["automatic", "manual"] | None = None,
    crop_vertical: bool | None = None,
    generate_highlights: bool | None = None,
    generate_metadata: bool | None = None,
    generate_subtitles: bool | None = None,
    context_aware: bool | None = None,
    output_preset: Literal["original", "tiktok", "reels", "youtube_shorts", "square", "landscape"] | None = None,
    visual_style: Literal["clean", "blur", "crop", "zoom", "split"] | None = None,
    subtitle_style: Literal["standard", "karaoke"] | None = None,
    hook_text: str | None = None,
    render_acceleration: Literal["auto", "cpu", "gpu"] | None = None,
) -> JobProcessingOptions:
    defaults = default_processing_options().model_dump()
    try:
        return JobProcessingOptions.model_validate(
            {
                "min_clip_seconds": (
                    min_clip_seconds if min_clip_seconds is not None else defaults["min_clip_seconds"]
                ),
                "max_clip_seconds": (
                    max_clip_seconds if max_clip_seconds is not None else defaults["max_clip_seconds"]
                ),
                "clip_count": clip_count if clip_count is not None else defaults["clip_count"],
                "metadata_language": (
                    metadata_language
                    if metadata_language is not None
                    else defaults["metadata_language"]
                ),
                "processing_mode": (
                    processing_mode
                    if processing_mode is not None
                    else defaults["processing_mode"]
                ),
                "crop_vertical": (
                    crop_vertical
                    if crop_vertical is not None
                    else defaults["crop_vertical"]
                ),
                "generate_highlights": (
                    generate_highlights
                    if generate_highlights is not None
                    else defaults["generate_highlights"]
                ),
                "generate_metadata": (
                    generate_metadata
                    if generate_metadata is not None
                    else defaults["generate_metadata"]
                ),
                "generate_subtitles": (
                    generate_subtitles
                    if generate_subtitles is not None
                    else defaults["generate_subtitles"]
                ),
                "context_aware": (
                    context_aware if context_aware is not None else defaults["context_aware"]
                ),
                "output_preset": (
                    output_preset if output_preset is not None else defaults["output_preset"]
                ),
                "visual_style": (
                    visual_style if visual_style is not None else defaults["visual_style"]
                ),
                "subtitle_style": (
                    subtitle_style if subtitle_style is not None else defaults["subtitle_style"]
                ),
                "hook_text": hook_text if hook_text is not None else defaults["hook_text"],
                "render_acceleration": (
                    render_acceleration
                    if render_acceleration is not None
                    else defaults["render_acceleration"]
                ),
            }
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
