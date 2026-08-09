"""Local operational endpoints for monitoring the personal ClipGen instance."""
import asyncio

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.database import get_db
from app.models import Clip, Job
from app.services.job_queue import get_job_queue
from app.services.maintenance import cleanup_temporary_files

router = APIRouter()


@router.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Return aggregate counts and storage usage without exposing source paths."""
    job_counts = dict(db.query(Job.status, func.count(Job.id)).group_by(Job.status).all())
    clip_counts = dict(db.query(Clip.status, func.count(Clip.id)).group_by(Clip.status).all())
    job_queue = get_job_queue()

    return {
        "queue": job_queue.status(),
        "jobs": job_counts,
        "clips": clip_counts,
        "storage_bytes": {
            "uploads": _directory_size(settings.upload_dir),
            "clips": _directory_size(settings.clips_dir),
            "temp": _directory_size(settings.temp_dir),
        },
    }


@router.get("/release")
async def get_release_info():
    """Return release metadata useful for UI display and support/debugging."""
    return {
        "name": "ClipGen",
        "version": settings.app_version,
        "release_channel": "local-mvp",
        "environment": "single-user-local",
        "limits": {
            "max_upload_size_mb": settings.max_upload_size_mb,
            "youtube_download_timeout_seconds": settings.youtube_download_timeout_seconds,
            "temp_file_retention_hours": settings.temp_file_retention_hours,
        },
        "defaults": {
            "metadata_language": settings.metadata_default_language,
            "whisper_model_size": settings.whisper_model_size,
            "whisper_device": settings.whisper_device,
        },
        "features": {
            "local_upload": True,
            "youtube_url": True,
            "upload_subtitles": False,
            "youtube_subtitles": True,
            "vertical_crop": True,
            "youtube_manual_options": True,
            "metadata_language_selector": True,
            "playwright_e2e": True,
        },
        "known_risks": [
            "YouTube extraction can change or be rate-limited by the source platform.",
            "Active in-process jobs are retryable after restart, but not resumable from checkpoints.",
            "Long CPU-bound videos can require Docker resource monitoring.",
        ],
    }


@router.post("/maintenance/cleanup")
async def run_cleanup():
    """Run temp/intermediate cleanup immediately for local QA/devops checks."""
    report = await asyncio.to_thread(cleanup_temporary_files)
    return {
        "files_deleted": report.files_deleted,
        "bytes_reclaimed": report.bytes_reclaimed,
    }


@router.get("/performance")
async def get_performance_baseline(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Summarize completed job timings for Sprint 3 performance checks."""
    jobs = (
        db.query(Job)
        .filter(Job.status == "done", Job.processing_started_at.isnot(None), Job.completed_at.isnot(None))
        .order_by(Job.completed_at.desc())
        .limit(limit)
        .all()
    )

    rows = []
    total_seconds = []
    source_durations = []
    stage_totals: dict[str, list[float]] = {}
    for job in jobs:
        processing_seconds = max(0.0, (job.completed_at - job.processing_started_at).total_seconds())
        total_seconds.append(processing_seconds)
        if job.source_duration_seconds:
            source_durations.append(float(job.source_duration_seconds))
        for stage, value in job.stage_metrics.items():
            stage_totals.setdefault(stage, []).append(float(value))
        rows.append(
            {
                "id": job.id,
                "source_type": job.source_type,
                "source_duration_seconds": job.source_duration_seconds,
                "processing_seconds": round(processing_seconds, 2),
                "stage_metrics": job.stage_metrics,
                "completed_at": job.completed_at,
                "warning_message": job.warning_message,
            }
        )

    return {
        "jobs_analyzed": len(rows),
        "total_processing_seconds": _summary(total_seconds),
        "source_duration_seconds": _summary(source_durations),
        "stage_seconds": {
            stage: _summary(values)
            for stage, values in sorted(stage_totals.items())
        },
        "latest_jobs": rows,
    }


def _directory_size(directory) -> int:
    if not directory.exists():
        return 0
    total = 0
    for path in directory.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except FileNotFoundError:
                continue
    return total


def _summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }
