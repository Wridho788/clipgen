"""
Full job pipeline on real media with stable transcript/metadata fixtures.

Per docs/05 §2 the expensive, nondeterministic model (Whisper/Ollama) is
replaced by the recorded transcript of the same fixture; probing, audio
extraction, candidate generation, caption cue building, rendering, and export
validation all run for real.
"""
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.edit_model import ClipEdit
from app.core.pipeline.transcribe import Segment
from app.models import Base, Clip, Job
from app.services import clip_render_service, job_service
from app.services.job_service import JobService

FIXTURES = Path(__file__).parent / "fixtures" / "media"
pytestmark = [
    pytest.mark.media,
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed"),
]


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    for name in ("temp_dir", "clips_dir", "upload_dir"):
        path = tmp_path / name
        path.mkdir()
        monkeypatch.setattr(job_service.settings, name, path)
    monkeypatch.setattr(clip_render_service, "select_video_encoder", lambda acceleration="auto": "libx264")
    monkeypatch.setattr(job_service.settings, "watermark_enabled", False)
    raw = json.loads((FIXTURES / "speech_landscape.transcript.json").read_text())
    transcribe_calls = []

    def fake_transcribe(audio_path, **kwargs):
        transcribe_calls.append(Path(audio_path))
        assert Path(audio_path).exists()  # real audio extraction ran
        return [Segment(item["start"], item["end"], item["text"]) for item in raw]

    monkeypatch.setattr(job_service, "transcribe", fake_transcribe)
    monkeypatch.setattr(
        job_service,
        "generate_metadata",
        lambda text, language, tags, brief: {"title": text[:40], "caption": text[:120], "hashtags": ["clipgen"]},
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session, tmp_path, transcribe_calls
    session.close()
    engine.dispose()


def _job(session, source: Path, tmp_path: Path, **options) -> Job:
    target = tmp_path / "upload_dir" / f"job{source.suffix}"
    shutil.copy(source, target)
    job = Job(
        id=f"job-{source.stem}",
        source_type="upload",
        source_path=str(target),
        source_name=source.name,
        status="pending",
        progress=0,
        processing_options=json.dumps({
            "min_clip_seconds": 15, "max_clip_seconds": 25, "clip_count": 2,
            "metadata_language": "en", "output_preset": "tiktok", "visual_style": "blur",
            "burn_captions": True, **options,
        }),
    )
    session.add(job)
    session.commit()
    return job


@pytest.mark.asyncio
async def test_pipeline_creates_sentence_aligned_editable_validated_clips(pipeline):
    session, tmp_path, transcribe_calls = pipeline
    job = _job(session, FIXTURES / "speech_landscape.mp4", tmp_path)

    await JobService(job.id, session).process()

    session.refresh(job)
    assert job.status == "done", job.error_message
    assert job.error_code is None
    assert len(transcribe_calls) == 1
    summary = job.automatic_summary["transcript"]
    assert summary["dropped_invalid"] >= 1  # hallucinated tail removed
    transcript = json.loads(job.transcript_json)
    assert all(segment["end"] <= job.source_duration_seconds for segment in transcript)

    clips = session.query(Clip).filter(Clip.job_id == job.id).order_by(Clip.position).all()
    assert len(clips) == 2
    segment_starts = {round(max(0.0, segment["start"] - 0.15), 3) for segment in transcript}
    for clip in clips:
        assert clip.status == "ready"
        assert clip.review_status == "suggested"
        assert clip.algorithm_version == "transcript-boundary-v1"
        assert clip.suggested_start_time == clip.start_time
        assert round(clip.start_time, 3) in segment_starts  # starts on a sentence
        assert 15 <= clip.end_time - clip.start_time <= 25
        assert clip.edit_revision == clip.rendered_revision == 1
        edit = ClipEdit.model_validate_json(clip.edit_json)
        assert edit.captions.enabled and edit.captions.cues
        assert all(cue.original_text == cue.text for cue in edit.captions.cues)
        report = json.loads(clip.render_report_json)
        assert report["validation"]["ok"] is True
        assert (report["validation"]["width"], report["validation"]["height"]) == (1080, 1920)
        assert report["captions_rendered"] > 0
        assert Path(clip.file_path).exists()
        analysis = json.loads(clip.analysis_json)
        assert analysis["explanation"] and analysis["rank"] in (1, 2)
        assert clip.title
    # No intermediate files are left behind.
    assert list((tmp_path / "temp_dir").iterdir()) == []


@pytest.mark.asyncio
async def test_rerender_after_edit_replaces_file_atomically(pipeline, monkeypatch):
    session, tmp_path, _ = pipeline
    job = _job(session, FIXTURES / "speech_landscape.mp4", tmp_path, clip_count=1)
    await JobService(job.id, session).process()
    clip = session.query(Clip).filter(Clip.job_id == job.id).one()
    first_file = Path(clip.file_path)

    edit = ClipEdit.model_validate_json(clip.edit_json)
    edit.captions.cues[0].text = "Corrected caption"
    edit = edit.model_copy(update={"trim_end_ms": edit.trim_start_ms + 16_000, "visual_style": "crop"})
    clip.edit_json = edit.model_dump_json()
    clip.edit_revision = 2
    session.commit()

    monkeypatch.setattr(clip_render_service, "SessionLocal", sessionmaker(bind=session.get_bind()))
    clip_render_service.render_saved_edit(clip.id)

    session.expire_all()
    clip = session.query(Clip).filter(Clip.id == clip.id).one()
    assert clip.rendered_revision == 2 and clip.status == "ready"
    assert clip.file_path.endswith("_r2.mp4")
    assert not first_file.exists()
    report = json.loads(clip.render_report_json)
    assert abs(report["validation"]["duration_seconds"] - 16.0) <= 0.35


@pytest.mark.asyncio
async def test_failed_rerender_keeps_previous_file_and_edit(pipeline, monkeypatch):
    session, tmp_path, _ = pipeline
    job = _job(session, FIXTURES / "speech_portrait.mp4", tmp_path, clip_count=1, min_clip_seconds=5,
               max_clip_seconds=10, burn_captions=False, generate_metadata=False)
    await JobService(job.id, session).process()
    clip = session.query(Clip).filter(Clip.job_id == job.id).one()
    previous_file = clip.file_path
    clip.edit_revision = 2
    session.commit()

    monkeypatch.setattr(clip_render_service, "SessionLocal", sessionmaker(bind=session.get_bind()))
    monkeypatch.setattr(clip_render_service, "select_video_encoder", lambda acceleration="auto": "no_such_encoder")
    clip_render_service.render_saved_edit(clip.id)

    session.expire_all()
    clip = session.query(Clip).filter(Clip.id == clip.id).one()
    assert clip.status == "ready"  # still usable
    assert clip.file_path == previous_file and Path(previous_file).exists()
    assert clip.render_error_code == "EXPORT_FAILED"
    assert clip.rendered_revision == 1 and clip.edit_revision == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fixture,options,code",
    [
        ("corrupt.mp4", {}, "SOURCE_CORRUPT"),
        ("no_audio.mp4", {"generate_metadata": True}, "AUDIO_MISSING"),
    ],
)
async def test_invalid_sources_fail_with_stable_codes(pipeline, fixture, options, code):
    session, tmp_path, _ = pipeline
    job = _job(session, FIXTURES / fixture, tmp_path, **options)
    await JobService(job.id, session).process()
    session.refresh(job)
    assert job.status == "failed"
    assert job.error_code == code
    assert "/app/storage" not in (job.error_message or "") and str(tmp_path) not in (job.error_message or "")
    assert session.query(Clip).filter(Clip.job_id == job.id).count() == 0


@pytest.mark.asyncio
async def test_no_audio_source_without_metadata_still_produces_clips(pipeline):
    session, tmp_path, transcribe_calls = pipeline
    job = _job(session, FIXTURES / "no_audio.mp4", tmp_path, generate_metadata=False, burn_captions=True,
               clip_count=1, min_clip_seconds=5, max_clip_seconds=8)
    await JobService(job.id, session).process()
    session.refresh(job)
    assert job.status == "done", job.error_message
    assert transcribe_calls == []  # nothing to transcribe
    clip = session.query(Clip).filter(Clip.job_id == job.id).one()
    assert clip.algorithm_version == "even-spacing-v1"
    assert json.loads(clip.render_report_json)["validation"]["has_audio"] is False


@pytest.mark.asyncio
async def test_transcription_failure_is_recoverable(pipeline, monkeypatch):
    session, tmp_path, _ = pipeline

    def broken(audio_path, **kwargs):
        raise RuntimeError("model crashed")

    monkeypatch.setattr(job_service, "transcribe", broken)
    job = _job(session, FIXTURES / "speech_portrait.mp4", tmp_path)
    await JobService(job.id, session).process()
    session.refresh(job)
    assert job.status == "failed" and job.error_code == "TRANSCRIPTION_FAILED"
    assert Path(job.source_path).exists()  # source preserved for a retry
    assert list((tmp_path / "temp_dir").iterdir()) == []  # temporary audio removed


@pytest.mark.asyncio
async def test_very_short_source_finishes_with_warning(pipeline):
    session, tmp_path, _ = pipeline
    job = _job(session, FIXTURES / "very_short.mp4", tmp_path, generate_metadata=False, burn_captions=False)
    await JobService(job.id, session).process()
    session.refresh(job)
    assert job.status == "done"
    assert job.warning_message
    assert job.automatic_summary["candidate_warning"] == "CANDIDATE_EMPTY"
