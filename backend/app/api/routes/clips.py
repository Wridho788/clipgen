"""
Routes: GET /api/clips, GET /api/clips/{id}, PATCH /api/clips/{id}, 
        DELETE /api/clips/{id}, GET /api/clips/{id}/file (download)
"""
import asyncio
import json
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Clip, Job
from app.core.pipeline.metadata_gen import generate_metadata
from app.schemas import ClipResponse, ClipUpdateRequest
from loguru import logger

router = APIRouter()


@router.get("/job/{job_id}", response_model=List[ClipResponse])
async def list_clips_by_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """List semua clip dari satu job."""
    clips = db.query(Clip).filter(Clip.job_id == job_id).order_by(Clip.created_at).all()
    return clips


@router.get("/job/{job_id}/archive")
async def download_job_archive(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Build a ZIP with all ready clips from a job for one-click export."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    clips = (
        db.query(Clip)
        .filter(Clip.job_id == job_id, Clip.status == "ready")
        .order_by(Clip.created_at)
        .all()
    )
    valid_clips = [clip for clip in clips if clip.file_path and Path(clip.file_path).exists()]
    if not valid_clips:
        raise HTTPException(status_code=409, detail="Belum ada clip siap untuk diunduh")

    archive_dir = settings.temp_dir / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"clipgen-{job_id}-{uuid.uuid4().hex}.zip"
    await asyncio.to_thread(_build_job_archive, archive_path, valid_clips)

    return FileResponse(
        path=archive_path,
        filename=f"clipgen-{job_id[:8]}.zip",
        media_type="application/zip",
        background=BackgroundTask(archive_path.unlink, missing_ok=True),
    )


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: str,
    db: Session = Depends(get_db),
):
    """Get clip detail."""
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    return clip


@router.patch("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: str,
    data: ClipUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Update metadata clip (title, caption, hashtags).
    User bisa override hasil AI generation.
    """
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")

    if data.title is not None:
        clip.title = data.title
    if data.caption is not None:
        clip.caption = data.caption
    if data.hashtags is not None:
        clip.hashtags = json.dumps(data.hashtags)

    db.commit()
    logger.info(f"Clip {clip_id} updated")
    return clip


@router.post("/{clip_id}/regenerate-metadata", response_model=ClipResponse)
async def regenerate_clip_metadata(
    clip_id: str,
    db: Session = Depends(get_db),
):
    """Regenerate title, caption, and hashtags from the stored job transcript."""
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    if clip.status != "ready":
        raise HTTPException(status_code=409, detail="Metadata hanya bisa dibuat ulang untuk clip yang siap")

    job = db.query(Job).filter(Job.id == clip.job_id).first()
    transcript_text = _get_clip_transcript_text(job, clip)
    if not transcript_text:
        raise HTTPException(
            status_code=409,
            detail="Transkrip job tidak tersedia untuk membuat metadata ulang.",
        )

    metadata = await asyncio.to_thread(
        generate_metadata,
        transcript_text,
        _metadata_language_for_job(job),
    )
    clip.title = metadata.get("title")
    clip.caption = metadata.get("caption")
    clip.hashtags = json.dumps(metadata.get("hashtags", []))
    if job:
        job.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(clip)
    logger.info(f"Clip {clip_id} metadata regenerated")
    return clip


@router.delete("/{clip_id}")
async def delete_clip(
    clip_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete clip (dan file videonya).
    """
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")

    # Delete file
    if clip.file_path:
        from pathlib import Path
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
):
    """
    Download clip video file.
    
    Return: MP4 file sebagai binary stream.
    Browser akan trigger download atau bisa juga embed di <video> tag.
    """
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")

    if not clip.file_path:
        raise HTTPException(status_code=400, detail="Clip belum siap (file_path kosong)")

    from pathlib import Path
    file_path = Path(clip.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File clip tidak ditemukan di storage")

    # Filename untuk download
    filename = _safe_download_filename(clip.title)
    filename = f"{filename}.mp4"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="video/mp4",
    )


@router.get("/{clip_id}/preview")
async def preview_clip(
    clip_id: str,
    db: Session = Depends(get_db),
):
    """
    Stream clip untuk preview di web player.
    Same file, but dengan Content-Range header support untuk seeking.
    
    (FastAPI + Starlette automatically handle streaming + range requests)
    """
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")

    if not clip.file_path:
        raise HTTPException(status_code=400, detail="Clip belum siap (file_path kosong)")

    from pathlib import Path
    file_path = Path(clip.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File clip tidak ditemukan")

    return FileResponse(
        path=file_path,
        media_type="video/mp4",
    )


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
