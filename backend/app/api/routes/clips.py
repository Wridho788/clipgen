"""
Routes: GET /api/clips, GET /api/clips/{id}, PATCH /api/clips/{id}, 
        DELETE /api/clips/{id}, GET /api/clips/{id}/file (download)
"""
import asyncio
import json
import re
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models import Clip, ClipFeedback, Job, User
from app.api.media_response import media_file_response
from app.core.errors import ErrorCode, PipelineError
from app.core.pipeline.metadata_gen import generate_metadata
from app.core.timeline import seconds_to_ms
from app.schemas import (
    ClipEditSaveRequest,
    ClipFeedbackRequest,
    ClipFeedbackResponse,
    ClipOrderRequest,
    ClipResponse,
    ClipReviewRequest,
    ClipTrimRequest,
    ClipUpdateRequest,
    JobProcessingOptions,
    default_processing_options,
)
from loguru import logger
from app.services.clip_editing import (
    candidate_payload,
    is_render_stale,
    load_edit,
    mark_exported,
    save_edit,
    set_review,
    store_edit,
)
from app.services.clip_render_service import enqueue_clip_render
from app.services.distribution_metadata import build_distribution_pack
from app.services.source_metadata import load_youtube_reference_hashtags
from app.services.campaign_compliance import evaluate_campaign_compliance

router = APIRouter()


@router.get("/job/{job_id}", response_model=List[ClipResponse])
def list_clips_by_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List semua clip dari satu job."""
    job = _get_owned_job(db, job_id, current_user)
    clips = _ordered_clips(db, job_id)
    return [_clip_response(clip, job) for clip in clips]


@router.post("/job/{job_id}/order", response_model=List[ClipResponse])
def reorder_clips(
    job_id: str,
    data: ClipOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a user-chosen candidate order."""
    job = _get_owned_job(db, job_id, current_user)
    clips = {clip.id: clip for clip in db.query(Clip).filter(Clip.job_id == job_id).all()}
    if set(data.clip_ids) != set(clips) or len(data.clip_ids) != len(clips):
        raise HTTPException(status_code=422, detail="Urutan harus berisi semua clip job ini tepat satu kali")
    for index, clip_id in enumerate(data.clip_ids, start=1):
        clips[clip_id].position = index
    db.commit()
    return [_clip_response(clip, job) for clip in _ordered_clips(db, job_id)]


@router.get("/job/{job_id}/archive")
async def download_job_archive(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Build a ZIP with all ready, non-rejected clips in the user's order."""
    _get_owned_job(db, job_id, current_user)  # ownership check

    clips = [
        clip for clip in _ordered_clips(db, job_id)
        if clip.status == "ready" and clip.review_status != "rejected"
    ]
    valid_clips = [clip for clip in clips if clip.file_path and Path(clip.file_path).exists()]
    if not valid_clips:
        raise HTTPException(status_code=409, detail="Belum ada clip siap untuk diunduh")

    archive_dir = settings.temp_dir / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"clipgen-{job_id}-{uuid.uuid4().hex}.zip"
    await asyncio.to_thread(_build_job_archive, archive_path, valid_clips)
    for clip in valid_clips:
        mark_exported(clip)
    db.commit()

    return FileResponse(
        path=archive_path,
        filename=f"clipgen-{job_id[:8]}.zip",
        media_type="application/zip",
        background=BackgroundTask(archive_path.unlink, missing_ok=True),
    )


@router.get("/{clip_id}", response_model=ClipResponse)
def get_clip(
    clip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get clip detail."""
    clip = _get_owned_clip(db, clip_id, current_user)
    return _clip_response(clip)


@router.patch("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: str,
    data: ClipUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update metadata clip (title, caption, hashtags).
    User bisa override hasil AI generation.
    """
    clip = _get_owned_clip(db, clip_id, current_user)

    if data.title is not None:
        clip.title = data.title
    if data.caption is not None:
        clip.caption = data.caption
    if data.hashtags is not None:
        clip.hashtags = json.dumps(data.hashtags)

    db.commit()
    logger.info(f"Clip {clip_id} updated")
    return _clip_response(clip)


@router.post("/{clip_id}/regenerate-metadata", response_model=ClipResponse)
async def regenerate_clip_metadata(
    clip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate title, caption, and hashtags from the stored job transcript."""
    clip = _get_owned_clip(db, clip_id, current_user)
    if clip.status != "ready":
        raise HTTPException(status_code=409, detail="Metadata hanya bisa dibuat ulang untuk clip yang siap")

    job = db.query(Job).filter(Job.id == clip.job_id).first()
    transcript_text = _get_clip_transcript_text(job, clip)
    if not transcript_text:
        raise HTTPException(
            status_code=409,
            detail="Transkrip job tidak tersedia untuk membuat metadata ulang.",
        )

    reference_hashtags = (
        load_youtube_reference_hashtags(job.source_path)
        if job and job.source_type == "youtube_url"
        else []
    )
    metadata = await asyncio.to_thread(
        generate_metadata,
        transcript_text,
        _metadata_language_for_job(job),
        reference_hashtags,
        _campaign_brief_for_job(job),
    )
    clip.title = metadata.get("title")
    clip.caption = metadata.get("caption")
    clip.hashtags = json.dumps(metadata.get("hashtags", []))
    if job:
        job.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(clip)
    logger.info(f"Clip {clip_id} metadata regenerated")
    return _clip_response(clip, job)


@router.delete("/{clip_id}")
async def delete_clip(
    clip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete clip (dan file videonya).
    """
    clip = _get_owned_clip(db, clip_id, current_user)

    # Delete file
    if clip.file_path:
        file_path = Path(clip.file_path)
        try:
            file_path.unlink()
            logger.info(f"Deleted clip file: {clip.file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete clip file: {e}")

    # Delete DB record
    db.delete(clip)
    db.commit()
    logger.info(f"Clip {clip_id} deleted from DB")
    return {"status": "deleted", "clip_id": clip_id}


@router.get("/{clip_id}/file")
async def download_clip(
    clip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the exported MP4 and record the export for review metrics."""
    clip = _get_owned_clip(db, clip_id, current_user)
    file_path = _ready_file(clip)
    mark_exported(clip)
    db.commit()
    return FileResponse(
        path=file_path,
        filename=f"{_safe_download_filename(clip.title)}.mp4",
        media_type="video/mp4",
    )


@router.get("/{clip_id}/preview")
async def preview_clip(
    clip_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the rendered clip with byte-range support for seeking."""
    clip = _get_owned_clip(db, clip_id, current_user)
    return media_file_response(request, _ready_file(clip))


@router.get("/{clip_id}/source")
async def stream_clip_source(
    clip_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the original source so the editor can preview unsaved-to-file edits live."""
    clip = _get_owned_clip(db, clip_id, current_user)
    job = _get_owned_job(db, clip.job_id, current_user)
    source = Path(job.source_path)
    if not source.exists():
        raise HTTPException(status_code=404, detail="File sumber tidak tersedia")
    media_type = {
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
    }.get(source.suffix.lower(), "video/mp4")
    return media_file_response(request, source, media_type)


@router.get("/{clip_id}/feedback", response_model=ClipFeedbackResponse)
async def get_clip_feedback(
    clip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = _get_owned_clip(db, clip_id, current_user)
    current = (
        db.query(ClipFeedback)
        .filter(ClipFeedback.clip_id == clip.id, ClipFeedback.user_id == current_user.id)
        .first()
    )
    positive_count, negative_count = _feedback_counts(db, clip.id)
    return ClipFeedbackResponse(
        rating=current.rating if current else None,
        reason=current.reason if current else None,
        positive_count=positive_count,
        negative_count=negative_count,
    )


@router.put("/{clip_id}/feedback", response_model=ClipFeedbackResponse)
async def rate_clip(
    clip_id: str,
    data: ClipFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store one quality signal per user so automatic selection can be tuned."""
    clip = _get_owned_clip(db, clip_id, current_user)
    feedback = (
        db.query(ClipFeedback)
        .filter(ClipFeedback.clip_id == clip.id, ClipFeedback.user_id == current_user.id)
        .first()
    )
    if feedback is None:
        feedback = ClipFeedback(clip_id=clip.id, user_id=current_user.id, rating=data.rating)
        db.add(feedback)
    feedback.rating = data.rating
    feedback.reason = data.reason.strip() if data.reason else None
    db.commit()
    positive_count, negative_count = _feedback_counts(db, clip.id)
    return ClipFeedbackResponse(
        rating=data.rating,
        reason=feedback.reason,
        positive_count=positive_count,
        negative_count=negative_count,
    )


@router.post("/{clip_id}/trim", response_model=ClipResponse, status_code=202)
async def trim_clip(
    clip_id: str,
    data: ClipTrimRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Backward-compatible trim: updates the saved edit, then re-renders it."""
    clip = _get_owned_clip(db, clip_id, current_user)
    job = _get_owned_job(db, clip.job_id, current_user)
    if job.source_duration_seconds and data.end_time > job.source_duration_seconds:
        raise HTTPException(status_code=422, detail="Timestamp akhir melebihi durasi video sumber")
    _require_source(job)
    edit = load_edit(clip, job).model_copy(
        update={"trim_start_ms": seconds_to_ms(data.start_time), "trim_end_ms": seconds_to_ms(data.end_time)}
    )
    save_edit(clip, job, edit, int(clip.edit_revision or 0))
    clip.status = "processing"
    db.commit()
    db.refresh(clip)
    await enqueue_clip_render(clip.id)
    return _clip_response(clip, job)


@router.put("/{clip_id}/edit", response_model=ClipResponse)
def save_clip_edit(
    clip_id: str,
    data: ClipEditSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Autosave the canonical edit. Stale ``base_revision`` returns 409 EDIT_CONFLICT."""
    clip = _get_owned_clip(db, clip_id, current_user)
    job = _get_owned_job(db, clip.job_id, current_user)
    save_edit(clip, job, data.edit, data.base_revision)
    db.commit()
    db.refresh(clip)
    return _clip_response(clip, job)


@router.post("/{clip_id}/render", response_model=ClipResponse, status_code=202)
async def render_clip(
    clip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue an export of the *saved* edit revision (never transient UI state)."""
    clip = _get_owned_clip(db, clip_id, current_user)
    job = _get_owned_job(db, clip.job_id, current_user)
    _require_source(job)
    if clip.status == "processing":
        raise HTTPException(status_code=409, detail="Render clip ini masih berjalan")
    if clip.edit_json is None:
        store_edit(clip, load_edit(clip, job))
        clip.edit_revision = int(clip.edit_revision or 0) + 1
    clip.status = "processing"
    clip.render_error_code = None
    clip.render_error_message = None
    db.commit()
    db.refresh(clip)
    await enqueue_clip_render(clip.id)
    return _clip_response(clip, job)


@router.post("/{clip_id}/review", response_model=ClipResponse)
def review_clip(
    clip_id: str,
    data: ClipReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept, reject (with a reason code), or reset a candidate."""
    clip = _get_owned_clip(db, clip_id, current_user)
    set_review(clip, data.status, data.reason)
    db.commit()
    db.refresh(clip)
    return _clip_response(clip)


@router.post("/{clip_id}/duplicate", response_model=ClipResponse, status_code=201)
def duplicate_clip(
    clip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Copy a candidate (edit, metadata, and current file) to try an alternative."""
    clip = _get_owned_clip(db, clip_id, current_user)
    job = _get_owned_job(db, clip.job_id, current_user)
    edit = load_edit(clip, job)
    copy = Clip(
        job_id=clip.job_id,
        start_time=clip.start_time,
        end_time=clip.end_time,
        suggested_start_time=clip.suggested_start_time,
        suggested_end_time=clip.suggested_end_time,
        highlight_score=clip.highlight_score,
        analysis_json=clip.analysis_json,
        algorithm_version=clip.algorithm_version,
        review_status="suggested",
        edit_revision=1,
        title=f"{clip.title} (salinan)" if clip.title else None,
        caption=clip.caption,
        hashtags=clip.hashtags,
        status="ready" if clip.file_path else clip.status,
    )
    store_edit(copy, edit)
    db.add(copy)
    db.flush()
    if clip.file_path and Path(clip.file_path).exists():
        target = settings.clips_dir / f"{copy.id}_r1.mp4"
        shutil.copy2(clip.file_path, target)
        copy.file_path = str(target)
        copy.rendered_revision = 1 if not is_render_stale(clip) else 0
        copy.render_report_json = clip.render_report_json
    else:
        copy.file_path = None
        copy.status = "failed"
    siblings = _ordered_clips(db, clip.job_id)
    order = [item.id for item in siblings if item.id != copy.id]
    order.insert(order.index(clip.id) + 1, copy.id)
    by_id = {item.id: item for item in siblings}
    by_id[copy.id] = copy
    for index, item_id in enumerate(order, start=1):
        by_id[item_id].position = index
    db.commit()
    db.refresh(copy)
    return _clip_response(copy, job)


def _clip_response(clip: Clip, job: Job | None = None) -> ClipResponse:
    """Expose one copy-ready manual distribution package per clip."""
    job = job or clip.job
    try:
        tags = json.loads(clip.hashtags or "[]")
    except json.JSONDecodeError:
        tags = []
    reference_tags = (
        load_youtube_reference_hashtags(job.source_path)
        if job and job.source_type == "youtube_url"
        else []
    )
    campaign_brief = _campaign_brief_for_job(job)
    effective_tags = tags if isinstance(tags, list) else []
    distribution = build_distribution_pack(
        clip.title,
        clip.caption,
        effective_tags,
        source_reference_hashtags=reference_tags,
        source_name=job.source_name if job else None,
        campaign_brief=campaign_brief,
    )
    compliance = evaluate_campaign_compliance(
        campaign_brief,
        transcript_text=_get_clip_transcript_text(job, clip),
        title=clip.title,
        caption=clip.caption,
        hashtags=[*effective_tags, *(campaign_brief.hashtags if campaign_brief else [])],
        duration_seconds=max(0.0, clip.end_time - clip.start_time),
    )
    if compliance is not None:
        distribution["compliance"] = compliance
    try:
        render_report = json.loads(clip.render_report_json or "null")
    except json.JSONDecodeError:
        render_report = None
    return ClipResponse.model_validate(clip).model_copy(
        update={
            "distribution": distribution,
            "candidate": candidate_payload(clip),
            "edit": load_edit(clip, job),
            "edit_revision": int(clip.edit_revision or 0),
            "render_stale": is_render_stale(clip),
            "render_report": render_report if isinstance(render_report, dict) else None,
            "review_status": clip.review_status or "suggested",
        }
    )


def _ordered_clips(db: Session, job_id: str) -> list[Clip]:
    clips = db.query(Clip).filter(Clip.job_id == job_id).order_by(Clip.created_at).all()
    return sorted(clips, key=lambda clip: (clip.position is None, clip.position or 0))


def _ready_file(clip: Clip) -> Path:
    if not clip.file_path:
        raise HTTPException(status_code=400, detail="Clip belum siap (file_path kosong)")
    file_path = Path(clip.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File clip tidak ditemukan di storage")
    return file_path


def _require_source(job: Job) -> None:
    if not Path(job.source_path).exists():
        raise PipelineError(ErrorCode.SOURCE_MISSING, message="File sumber tidak tersedia untuk membuat render baru")


def _get_owned_job(db: Session, job_id: str, current_user: User) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == current_user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


def _get_owned_clip(db: Session, clip_id: str, current_user: User) -> Clip:
    clip = (
        db.query(Clip)
        .join(Job, Clip.job_id == Job.id)
        .filter(Clip.id == clip_id, Job.owner_id == current_user.id)
        .first()
    )
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    return clip


def _feedback_counts(db: Session, clip_id: str) -> tuple[int, int]:
    rows = (
        db.query(ClipFeedback.rating, func.count(ClipFeedback.id))
        .filter(ClipFeedback.clip_id == clip_id)
        .group_by(ClipFeedback.rating)
        .all()
    )
    counts = {int(rating): int(count) for rating, count in rows}
    return counts.get(1, 0), counts.get(-1, 0)


def _safe_download_filename(title: str | None) -> str:
    """Make AI/user-generated titles safe for Content-Disposition filenames."""
    if not title:
        return "clip"
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", title.strip()).strip("._")
    return (filename or "clip")[:50]


def _build_job_archive(archive_path: Path, clips: list[Clip]) -> None:
    """Write a temporary ZIP outside the event loop, then let FileResponse stream it."""
    archive_path.unlink(missing_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, clip in enumerate(clips, start=1):
            file_path = Path(clip.file_path)
            filename = _safe_download_filename(clip.title)
            archive.write(file_path, arcname=f"{index:02d}-{filename}-{clip.id[:8]}.mp4")


def _get_clip_transcript_text(job: Job | None, clip: Clip) -> str:
    if not job or not job.transcript_json:
        return ""
    try:
        segments = json.loads(job.transcript_json)
    except json.JSONDecodeError:
        logger.warning(f"Job {job.id}: transcript_json invalid")
        return ""

    if not isinstance(segments, list):
        return ""

    relevant_text = []
    for segment in segments:
        try:
            start = float(segment["start"])
            end = float(segment["end"])
            text = str(segment["text"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if text and start < clip.end_time and end > clip.start_time:
            relevant_text.append(text)
    return " ".join(relevant_text)


def _metadata_language_for_job(job: Job | None) -> str:
    if not job:
        return "id"
    try:
        options = json.loads(job.processing_options or "{}")
    except json.JSONDecodeError:
        return "id"
    return "en" if isinstance(options, dict) and options.get("metadata_language") == "en" else "id"


def _campaign_brief_for_job(job: Job | None):
    if not job:
        return None
    try:
        stored = json.loads(job.processing_options or "{}")
        if not isinstance(stored, dict) or not stored.get("campaign_brief"):
            return None
        defaults = default_processing_options().model_dump()
        options = JobProcessingOptions.model_validate({**defaults, **stored})
        return options.campaign_brief
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
