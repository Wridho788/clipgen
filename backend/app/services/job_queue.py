"""
In-Process Job Queue.

Untuk personal single-user, tidak perlu Celery+Redis.
Gunakan asyncio.Queue dengan background worker thread.
Job queue ini interface generic, bisa di-swap ke Celery nanti kalau perlu.

Design:
  - Frontend POST /api/videos/upload → create Job, enqueue ke JobQueue
  - Background worker pull dari queue, call JobService.process()
  - Frontend polling GET /api/jobs/{id} untuk status
"""
import asyncio
import inspect
from typing import Callable
from dataclasses import dataclass
from datetime import datetime
from loguru import logger


@dataclass
class JobTask:
    """Satu item di queue."""
    job_id: str
    process_func: Callable  # async function yang jalankan JobService.process()


class InProcessJobQueue:
    """Single-threaded, in-memory job queue."""

    def __init__(self, max_workers: int = 1):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_workers = max_workers
        self._worker_task = None
        self._worker_started_at: datetime | None = None
        self._current_job_id: str | None = None
        self._current_job_started_at: datetime | None = None
        self._processed_jobs = 0
        self._failed_jobs = 0
        self._cancelled_job_ids: set[str] = set()
        self._skipped_cancelled_jobs = 0

    async def enqueue(self, job_id: str, process_func: Callable):
        """Tambah job ke queue."""
        task = JobTask(job_id=job_id, process_func=process_func)
        await self.queue.put(task)
        logger.info(f"Job {job_id} enqueued, queue size: {self.queue.qsize()}")

    def cancel(self, job_id: str) -> None:
        """Mark an in-memory task as cancelled so a queued item is skipped.

        ``asyncio.Queue`` deliberately has no safe arbitrary-item removal API.
        Marking the task keeps queue accounting intact while making its executable
        queue size immediately accurate and prevents the pipeline from starting it.
        """
        self._cancelled_job_ids.add(job_id)

    async def start_worker(self):
        """Jalankan worker loop. Panggil ini saat FastAPI startup."""
        if self._worker_task and not self._worker_task.done():
            return  # sudah running
        
        self._worker_started_at = datetime.utcnow()
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Job queue worker started")

    async def _worker_loop(self):
        """Infinite loop: pull dari queue, process, repeat."""
        while True:
            task: JobTask = await self.queue.get()
            if task.job_id in self._cancelled_job_ids:
                self._cancelled_job_ids.discard(task.job_id)
                self._skipped_cancelled_jobs += 1
                logger.info(f"Worker: skipped cancelled queued job {task.job_id}")
                self.queue.task_done()
                continue
            self._current_job_id = task.job_id
            self._current_job_started_at = datetime.utcnow()
            try:
                logger.info(f"Worker: processing job {task.job_id}")
                await asyncio.to_thread(self._run_process_func, task.process_func)
                self._processed_jobs += 1
                logger.info(f"Worker: job {task.job_id} done")
            except Exception as e:
                self._failed_jobs += 1
                logger.error(f"Worker error: {e}", exc_info=True)
            finally:
                self._current_job_id = None
                self._current_job_started_at = None
                self._cancelled_job_ids.discard(task.job_id)
                self.queue.task_done()

    @staticmethod
    def _run_process_func(process_func: Callable):
        """
        Run heavy pipeline work outside FastAPI's event loop.

        The video pipeline is mostly synchronous CPU/subprocess work. Running it
        directly inside the asyncio worker would block API polling while a job is
        extracting/transcribing/rendering.
        """
        result = process_func()
        if inspect.isawaitable(result):
            asyncio.run(result)

    async def stop_worker(self):
        """Stop worker loop. Panggil saat FastAPI shutdown."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._current_job_id = None
            self._current_job_started_at = None
            logger.info("Job queue worker stopped")

    def queue_size(self) -> int:
        """Return the number of queued jobs that can still execute."""
        return sum(
            1
            for task in self.queue._queue  # asyncio.Queue exposes a deque internally.
            if task.job_id not in self._cancelled_job_ids
        )

    def cancelled_queue_size(self) -> int:
        """Return cancelled entries waiting to be drained by the worker."""
        return sum(
            1
            for task in self.queue._queue
            if task.job_id in self._cancelled_job_ids
        )

    def position(self, job_id: str) -> int | None:
        """Return a one-based position among executable queued jobs.

        ``0`` denotes the job currently owned by the worker. ``None`` means the
        job is terminal, cancelled, or is not present in this process's queue.
        """
        if self._current_job_id == job_id:
            return 0
        if job_id in self._cancelled_job_ids:
            return None

        position = 0
        for task in self.queue._queue:
            if task.job_id in self._cancelled_job_ids:
                continue
            position += 1
            if task.job_id == job_id:
                return position
        return None

    def status(self) -> dict:
        """Operational snapshot used by health/metrics endpoints."""
        worker_running = bool(self._worker_task and not self._worker_task.done())
        return {
            "queue_size": self.queue_size(),
            "raw_queue_size": self.queue.qsize(),
            "cancelled_in_queue": self.cancelled_queue_size(),
            "worker_running": worker_running,
            "worker_started_at": self._worker_started_at,
            "current_job_id": self._current_job_id,
            "current_job_started_at": self._current_job_started_at,
            "processed_jobs": self._processed_jobs,
            "failed_jobs": self._failed_jobs,
            "skipped_cancelled_jobs": self._skipped_cancelled_jobs,
        }


# Global singleton instance
_job_queue: InProcessJobQueue = None


def get_job_queue() -> InProcessJobQueue:
    """Get atau create singleton job queue."""
    global _job_queue
    if _job_queue is None:
        _job_queue = InProcessJobQueue()
    return _job_queue
