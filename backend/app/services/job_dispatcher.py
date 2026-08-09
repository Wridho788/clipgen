"""Shared job dispatching so every route enqueues work consistently."""
from app.database import SessionLocal
from app.services.job_queue import get_job_queue
from app.services.job_service import JobService


async def enqueue_job(job_id: str) -> None:
    """Queue a persisted job and give the worker its own database session."""
    job_queue = get_job_queue()

    async def process_job():
        with SessionLocal() as worker_db:
            job_service = JobService(job_id, worker_db)
            await job_service.process()

    await job_queue.enqueue(job_id, process_job)
