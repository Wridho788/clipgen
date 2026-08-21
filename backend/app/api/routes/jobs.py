"""
Routes: GET /api/jobs, GET /api/jobs/{id}, POST /api/jobs/{id}/cancel
"""
import json
from pathlib import Path
from typing import List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user
from app.models import Job, User
from app.schemas import (
    JobCreateResponse,
    JobProcessingOptions,
    JobResponse,
    JobRetryRequest,
    default_processing_options,
)
from app.services.job_dispatcher import enqueue_job
from app.services.job_queue import get_job_queue
from app.services.processing_estimator import build_stage_estimates, total_estimate_seconds
from app.services.runtime_capabilities import get_runtime_capabilities

router = APIRouter()


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    status: str = None,  # filter by status
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List semua job.
    
    Query params:
      - status: filter (pending, done, failed, etc)
    """
    query = db.query(Job).filter(Job.owner_id == current_user.id)
    if status:
        query = query.filter(Job.status == status)
    
    jobs = query.order_by(Job.created_at.desc()).all()
    return [_job_response(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get job status + progress."""
    job = _get_owned_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _job_response(job)


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel job yang sedang berjalan.
    
    A queued item is skipped immediately. The isolated transcription stage also
    observes cancellation through its heartbeat and terminates its child process.
    """
    job = _get_owned_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status == "cancelled":
        return {"status": "cancelled", "job_id": job_id}

    if job.status == "done" or job.status == "failed":
        raise HTTPException(status_code=400, detail=f"Cannot cancel job dengan status {job.status}")

    # Mark sebagai cancelled
    job.status = "cancelled"
    job.error_message = "User cancelled"
    job.updated_at = datetime.utcnow()
    job.completed_at = job.updated_at
    job.stage_started_at = None
    job.heartbeat_at = job.updated_at
    db.commit()
    get_job_queue().cancel(job_id)

    return {"status": "cancelled", "job_id": job_id}


@router.post("/{job_id}/retry", response_model=JobCreateResponse)
async def retry_job(
    job_id: str,
    data: JobRetryRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new job from a terminal job without overwriting its existing result."""
    original_job = _get_owned_job(db, job_id, current_user)
    if not original_job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if original_job.status not in {"failed", "cancelled", "done"}:
        raise HTTPException(status_code=409, detail="Job masih berjalan dan belum bisa diproses ulang")

    source_path = Path(original_job.source_path)
    if original_job.source_type != "youtube_url" and not source_path.exists():
        raise HTTPException(
            status_code=409,
            detail="File sumber sudah tidak tersedia. Upload video lagi untuk membuat job baru.",
        )

    if data and data.processing_options:
        processing_options = data.processing_options
    else:
        try:
            stored_options = json.loads(original_job.processing_options or "{}")
        except json.JSONDecodeError:
            stored_options = {}
        defaults = default_processing_options().model_dump()
        processing_options = JobProcessingOptions.model_validate({**defaults, **stored_options})

    stage_estimates = build_stage_estimates(
        original_job.source_duration_seconds,
        original_job.source_type,
        processing_options,
    )

    retry = Job(
        owner_id=current_user.id,
        source_type=original_job.source_type,
        source_path=original_job.source_path,
        source_name=original_job.source_name or source_path.name,
        source_duration_seconds=original_job.source_duration_seconds,
        source_size_bytes=original_job.source_size_bytes,
        processing_options=processing_options.model_dump_json(),
        stage_estimates_json=json.dumps(stage_estimates),
        parent_job_id=original_job.parent_job_id or original_job.id,
        retry_count=(original_job.retry_count or 0) + 1,
        status="pending",
    )
    db.add(retry)
    db.commit()
    db.refresh(retry)

    await enqueue_job(retry.id)
    return JobCreateResponse(
        job_id=retry.id,
        status=retry.status,
        stage_estimates=stage_estimates,
        estimated_processing_seconds=total_estimate_seconds(stage_estimates),
    )


def _get_owned_job(db: Session, job_id: str, current_user: User) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


def _job_response(job: Job) -> JobResponse:
    """Attach volatile queue position without persisting queue state in SQLite."""
    response = JobResponse.model_validate(job)
    return response.model_copy(
        update={
            "queue_position": get_job_queue().position(job.id),
            # Processing uses auto mode. This is the device the active backend
            # can truly use, never a manual UI preference or build-only claim.
            "runtime": get_runtime_capabilities().as_dict(),
        }
    )
