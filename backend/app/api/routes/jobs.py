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
from app.models import Job
from app.schemas import (
    JobCreateResponse,
    JobProcessingOptions,
    JobResponse,
    JobRetryRequest,
    default_processing_options,
)
from app.services.job_dispatcher import enqueue_job
from app.services.processing_estimator import build_stage_estimates, total_estimate_seconds

router = APIRouter()


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    status: str = None,  # filter by status
    db: Session = Depends(get_db),
):
    """
    List semua job.
    
    Query params:
      - status: filter (pending, done, failed, etc)
    """
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    
    jobs = query.order_by(Job.created_at.desc()).all()
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Get job status + progress."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Cancel job yang sedang berjalan.
    
    Limitation (in-process queue): 
    Kalau job sedang di-process, tidak bisa di-interrupt mid-stage.
    Cuma bisa di-cancel kalau masih di queue (belum dimulai).
    
    TODO: implementasi yang lebih sophisticated (interruptible stages, checkpoint).
    """
    job = db.query(Job).filter(Job.id == job_id).first()
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
    db.commit()

    return {"status": "cancelled", "job_id": job_id}


@router.post("/{job_id}/retry", response_model=JobCreateResponse)
async def retry_job(
    job_id: str,
    data: JobRetryRequest | None = None,
    db: Session = Depends(get_db),
):
    """Create a new job from a terminal job without overwriting its existing result."""
    original_job = db.query(Job).filter(Job.id == job_id).first()
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
