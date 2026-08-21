"""Local operational endpoints for monitoring the personal ClipGen instance."""
import asyncio
import json
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models import Clip, ClipFeedback, Job, User
from app.schemas import StorageClearRequest
from app.services.job_queue import get_job_queue
from app.services.maintenance import (
    StorageBusyError,
    cleanup_temporary_files,
    clear_workspace_storage,
    storage_policy,
)
from app.services.runtime_capabilities import get_runtime_capabilities

router = APIRouter()


@router.get("/metrics")
async def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregate counts and storage usage without exposing source paths."""
    job_counts = dict(
        db.query(Job.status, func.count(Job.id))
        .filter(Job.owner_id == current_user.id)
        .group_by(Job.status)
        .all()
    )
    clip_counts = dict(
        db.query(Clip.status, func.count(Clip.id))
        .join(Job, Clip.job_id == Job.id)
        .filter(Job.owner_id == current_user.id)
        .group_by(Clip.status)
        .all()
    )
    job_queue = get_job_queue()

    return {
        "queue": job_queue.status(),
        "jobs": job_counts,
        "clips": clip_counts,
        "storage_bytes": {
            "uploads": _owned_source_size(db, current_user.id),
            "clips": _owned_clip_size(db, current_user.id),
            "temp": _directory_size(settings.temp_dir),
        },
        "storage_policy": storage_policy(),
        "feedback": {
            "positive": _feedback_count(db, current_user.id, 1),
            "negative": _feedback_count(db, current_user.id, -1),
        },
    }


@router.get("/release")
async def get_release_info():
    """Return release metadata useful for UI display and support/debugging."""
    capabilities = get_runtime_capabilities()
    return {
        "name": "ClipGen",
        "version": settings.app_version,
        "release_channel": "local-mvp",
        "environment": "single-user-local",
        "auth": {
            "enabled": settings.auth_enabled,
            "token_ttl_hours": settings.auth_token_ttl_hours,
        },
        "limits": {
            "max_upload_size_mb": settings.max_upload_size_mb,
            "youtube_download_timeout_seconds": settings.youtube_download_timeout_seconds,
            "temp_file_retention_hours": settings.temp_file_retention_hours,
            "upload_retention_days": settings.upload_retention_days,
            "clip_retention_days": settings.clip_retention_days,
        },
        "defaults": {
            "metadata_language": settings.metadata_default_language,
            "whisper_model_size": settings.whisper_model_size,
            "whisper_device": settings.whisper_device,
            "render_acceleration": settings.render_acceleration,
        },
        "acceleration": capabilities.as_dict(),
        "rendering": {
            "nvenc_available": capabilities.nvenc_runtime_usable,
            "cpu_fallback": True,
        },
        "features": {
            "local_upload": True,
            "youtube_url": True,
            "upload_subtitles": True,
            "youtube_subtitles": True,
            "vertical_crop": True,
            "context_aware_clipping": True,
            "social_reframe": True,
            "karaoke_subtitles": True,
            "hook_overlay": True,
            "platform_export_presets": True,
            "gpu_render_fallback": True,
            "youtube_manual_options": True,
            "youtube_automatic_multi_clip": True,
            "youtube_visual_intro_analysis": True,
            "metadata_language_selector": True,
            "playwright_e2e": True,
            "clip_quality_feedback": True,
            "local_multi_user": settings.auth_enabled,
        },
        "known_risks": [
            "YouTube extraction can change or be rate-limited by the source platform.",
            "Interrupted in-process jobs restart as a new linked retry job, not from a frame-level checkpoint.",
            "Long CPU-bound videos can require Docker resource monitoring.",
            "GPU rendering requires an NVENC-capable ffmpeg and a GPU exposed to the backend container.",
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


@router.post("/storage/clear")
def clear_storage(
    payload: StorageClearRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear stored assets/history only when no job can be affected."""
    try:
        report = clear_workspace_storage(db, current_user.id, payload.mode)
    except StorageBusyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "mode": report.mode,
        "files_handled": report.files_handled,
        "bytes_moved": report.bytes_moved,
        "bytes_reclaimed": report.bytes_reclaimed,
        "jobs_deleted": report.jobs_deleted,
        "clips_deleted": report.clips_deleted,
        "recycle_path": report.recycle_path,
    }


@router.get("/maintenance/policy")
async def get_storage_policy(current_user: User = Depends(get_current_user)):
    """Document current storage behavior for the active local workspace."""
    return storage_policy()


@router.get("/performance")
async def get_performance_baseline(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize completed job timings for Sprint 3 performance checks."""
    jobs = (
        db.query(Job)
        .filter(
            Job.owner_id == current_user.id,
            Job.status == "done",
            Job.processing_started_at.isnot(None),
            Job.completed_at.isnot(None),
        )
        .order_by(Job.completed_at.desc())
        .limit(limit)
        .all()
    )

    rows = []
    total_seconds = []
    source_durations = []
    stage_totals: dict[str, list[float]] = {}
    profiles: dict[str, dict[str, object]] = {}
    for job in jobs:
        processing_seconds = max(0.0, (job.completed_at - job.processing_started_at).total_seconds())
        total_seconds.append(processing_seconds)
        if job.source_duration_seconds:
            source_durations.append(float(job.source_duration_seconds))
        for stage, value in job.stage_metrics.items():
            stage_totals.setdefault(stage, []).append(float(value))
        try:
            options = json.loads(job.processing_options or "{}")
        except json.JSONDecodeError:
            options = {}
        profile = " · ".join(
            [
                job.source_type,
                str(options.get("output_preset", "original")),
                str(options.get("visual_style", "clean")),
                "subtitle" if options.get("generate_subtitles") else "no-subtitle",
            ]
        )
        profile_row = profiles.setdefault(
            profile,
            {"jobs": 0, "processing_seconds": [], "stage_seconds": {}},
        )
        profile_row["jobs"] = int(profile_row["jobs"]) + 1
        profile_row["processing_seconds"].append(processing_seconds)
        for stage, value in job.stage_metrics.items():
            profile_row["stage_seconds"].setdefault(stage, []).append(float(value))
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
        "profiles": [
            {
                "profile": profile,
                "jobs": values["jobs"],
                "processing_seconds": _summary(values["processing_seconds"]),
                "stage_seconds": {
                    stage: _summary(stage_values)
                    for stage, stage_values in sorted(values["stage_seconds"].items())
                },
            }
            for profile, values in sorted(profiles.items())
        ],
        "runtime_current": get_runtime_capabilities().as_dict(),
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


def _owned_source_size(db: Session, owner_id: str) -> int:
    paths = {
        job.source_path
        for job in db.query(Job).filter(Job.owner_id == owner_id).all()
        if job.source_path and not job.source_path.startswith(("http://", "https://"))
    }
    return _paths_size(paths)


def _owned_clip_size(db: Session, owner_id: str) -> int:
    paths = {
        clip.file_path
        for clip in db.query(Clip).join(Job, Clip.job_id == Job.id).filter(Job.owner_id == owner_id).all()
        if clip.file_path
    }
    return _paths_size(paths)


def _paths_size(paths: set[str]) -> int:
    total = 0
    for raw_path in paths:
        try:
            total += Path(raw_path).stat().st_size
        except OSError:
            continue
    return total


def _feedback_count(db: Session, owner_id: str, rating: int) -> int:
    return int(
        db.query(func.count(ClipFeedback.id))
        .join(Clip, ClipFeedback.clip_id == Clip.id)
        .join(Job, Clip.job_id == Job.id)
        .filter(Job.owner_id == owner_id, ClipFeedback.rating == rating)
        .scalar()
        or 0
    )
