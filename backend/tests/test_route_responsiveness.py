import inspect

import pytest

from app.api.routes import clips, jobs, system
from app.models import Job


@pytest.mark.parametrize(
    "handler",
    [
        jobs.list_jobs,
        jobs.get_job,
        clips.list_clips_by_job,
        clips.get_clip,
        system.get_metrics,
        system.get_performance_baseline,
    ],
)
def test_polled_routes_run_in_threadpool(handler):
    # These handlers do blocking SQLite and filesystem work. As plain `def`
    # FastAPI runs them in its threadpool instead of stalling the event loop
    # (which previously held uploads behind slow metrics polling).
    assert not inspect.iscoroutinefunction(handler)


def test_job_transcript_is_not_loaded_by_list_queries():
    assert Job.__mapper__.column_attrs["transcript_json"].deferred
