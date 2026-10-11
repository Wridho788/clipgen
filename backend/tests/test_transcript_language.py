"""Spoken-language handling: Whisper must not guess when the user knows.

Regression for an Indonesian TV show (music intro) that Whisper `tiny`
auto-detected as Catalan (p=0.45), producing Catalan captions and titles.
"""
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.videos import _processing_options_from_values
from app.core.pipeline.transcribe import Segment, TranscriptResult
from app.models import Base, Job
from app.schemas import JobProcessingOptions, default_processing_options
from app.services import job_service
from app.services.job_service import JobService

FIXTURES = Path(__file__).parent / "fixtures" / "media"


def _options(**overrides) -> JobProcessingOptions:
    return JobProcessingOptions.model_validate({**default_processing_options().model_dump(), **overrides})


def _result(language: str, probability: float) -> TranscriptResult:
    result = TranscriptResult([Segment(0.0, 1.0, "halo")])
    result.language = language
    result.language_probability = probability
    return result


def test_indonesian_is_the_default_audio_language():
    assert default_processing_options().transcript_language == "id"
    options = _processing_options_from_values(
        min_clip_seconds=None, max_clip_seconds=None, clip_count=None, metadata_language=None,
    )
    assert options.transcript_language == "id"


def test_audio_language_can_be_chosen_per_job():
    options = _processing_options_from_values(
        min_clip_seconds=None, max_clip_seconds=None, clip_count=None, metadata_language="id",
        transcript_language="en",
    )
    assert options.transcript_language == "en"
    assert options.metadata_language == "id"  # independent settings


def test_jobs_stored_before_the_option_default_to_indonesian():
    # Retried legacy jobs merge stored options over defaults.
    legacy = {"metadata_language": "id", "output_preset": "tiktok"}
    merged = JobProcessingOptions.model_validate({**default_processing_options().model_dump(), **legacy})
    assert merged.transcript_language == "id"


@pytest.mark.parametrize(
    "requested,detected,probability,warns",
    [
        ("auto", "ca", 0.45, True),   # the ARISAN case: unexpected language, low confidence
        ("auto", "ca", 0.95, True),   # confident but not a language we expect
        ("auto", "id", 0.40, True),   # expected language, low confidence
        ("auto", "id", 0.98, False),
        ("auto", "en", 0.90, False),
        ("id", "id", 1.00, False),    # explicit choice is trusted
    ],
)
def test_language_warning(requested, detected, probability, warns):
    warning = JobService._language_warning(_options(transcript_language=requested), _result(detected, probability))
    assert bool(warning) is warns
    if warns:
        assert detected in warning and "proses ulang" in warning


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    for name in ("temp_dir", "clips_dir", "upload_dir"):
        path = tmp_path / name
        path.mkdir()
        monkeypatch.setattr(job_service.settings, name, path)
    calls = []
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session, tmp_path, calls
    session.close()
    engine.dispose()


def _run_job(session, tmp_path, calls, monkeypatch, *, requested: str, detected: str, probability: float) -> Job:
    def fake_transcribe(audio_path, **kwargs):
        calls.append(kwargs.get("language"))
        return _result(detected, probability)

    monkeypatch.setattr(job_service, "transcribe", fake_transcribe)
    source = tmp_path / "upload_dir" / "short.mp4"
    shutil.copy(FIXTURES / "very_short.mp4", source)
    job = Job(
        id=f"job-{requested}", source_type="upload", source_path=str(source), status="pending", progress=0,
        processing_options=json.dumps({
            "min_clip_seconds": 5, "max_clip_seconds": 10, "generate_metadata": False,
            "burn_captions": True, "transcript_language": requested,
        }),
    )
    session.add(job)
    session.commit()
    return job


@pytest.mark.media
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
@pytest.mark.asyncio
async def test_pipeline_passes_language_and_records_detection(pipeline, monkeypatch):
    session, tmp_path, calls = pipeline
    job = _run_job(session, tmp_path, calls, monkeypatch, requested="id", detected="id", probability=1.0)
    await JobService(job.id, session).process()
    session.refresh(job)
    assert calls == ["id"]
    summary = job.automatic_summary["transcript"]
    assert summary["requested_language"] == "id"
    assert summary["language"] == "id" and summary["language_probability"] == 1.0


@pytest.mark.media
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
@pytest.mark.asyncio
async def test_auto_detection_of_unexpected_language_warns_without_losing_other_warnings(pipeline, monkeypatch):
    session, tmp_path, calls = pipeline
    job = _run_job(session, tmp_path, calls, monkeypatch, requested="auto", detected="ca", probability=0.45)
    await JobService(job.id, session).process()
    session.refresh(job)
    assert calls == [None]  # Whisper is asked to auto-detect
    assert job.status == "done"
    assert "'ca'" in job.warning_message
    assert "tidak cukup panjang" in job.warning_message  # 3 s source warning kept as well
