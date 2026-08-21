import asyncio
import threading
import time

import pytest

from app.services.job_queue import InProcessJobQueue


@pytest.mark.asyncio
async def test_worker_runs_blocking_jobs_off_event_loop():
    queue = InProcessJobQueue()
    completed = threading.Event()

    async def blocking_job():
        time.sleep(0.2)
        completed.set()

    await queue.start_worker()
    try:
        assert queue.status()["worker_running"] is True
        started_at = time.perf_counter()
        await queue.enqueue("job-1", blocking_job)

        await asyncio.sleep(0.05)
        elapsed = time.perf_counter() - started_at

        assert elapsed < 0.15
        assert queue.status()["current_job_id"] == "job-1"
        assert await asyncio.wait_for(asyncio.to_thread(completed.wait, 1), timeout=1)
        await asyncio.wait_for(queue.queue.join(), timeout=1)
        assert queue.status()["current_job_id"] is None
        assert queue.status()["processed_jobs"] == 1
    finally:
        await queue.stop_worker()
    assert queue.status()["worker_running"] is False


@pytest.mark.asyncio
async def test_cancelled_queued_job_is_not_counted_or_executed():
    queue = InProcessJobQueue()
    executed = False

    async def cancelled_job():
        nonlocal executed
        executed = True

    await queue.enqueue("cancelled-job", cancelled_job)
    await queue.enqueue("next-job", cancelled_job)
    queue.cancel("cancelled-job")

    assert queue.status()["queue_size"] == 1
    assert queue.status()["raw_queue_size"] == 2
    assert queue.status()["cancelled_in_queue"] == 1
    assert queue.position("cancelled-job") is None
    assert queue.position("next-job") == 1

    await queue.start_worker()
    try:
        await asyncio.wait_for(queue.queue.join(), timeout=1)
        assert executed is True
        assert queue.status()["skipped_cancelled_jobs"] == 1
    finally:
        await queue.stop_worker()
