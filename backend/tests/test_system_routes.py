from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import system
from app.models import Base, Clip, Job


def _session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'system.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.mark.asyncio
async def test_metrics_contract_includes_queue_counts_and_storage(monkeypatch, tmp_path):
    upload_dir = tmp_path / "uploads"
    clips_dir = tmp_path / "clips"
    temp_dir = tmp_path / "temp"
    for directory in (upload_dir, clips_dir, temp_dir):
        directory.mkdir()
    (upload_dir / "source.mp4").write_bytes(b"video")
    (clips_dir / "clip.mp4").write_bytes(b"clip")
    (temp_dir / "audio.wav").write_bytes(b"audio")

    monkeypatch.setattr(system.settings, "upload_dir", upload_dir)
    monkeypatch.setattr(system.settings, "clips_dir", clips_dir)
    monkeypatch.setattr(system.settings, "temp_dir", temp_dir)

    Session = _session(tmp_path)
    with Session() as db:
        db.add(Job(id="job-1", source_type="upload", source_path="/tmp/source.mp4", status="done"))
        db.add(Clip(id="clip-1", job_id="job-1", start_time=0, end_time=10, highlight_score=1, status="ready"))
        db.commit()

        response = await system.get_metrics(db)

    assert response["queue"]["queue_size"] >= 0
    assert "worker_running" in response["queue"]
    assert response["jobs"] == {"done": 1}
    assert response["clips"] == {"ready": 1}
    assert response["storage_bytes"] == {"uploads": 5, "clips": 4, "temp": 5}


@pytest.mark.asyncio
async def test_performance_baseline_contract_summarizes_completed_jobs(tmp_path):
    Session = _session(tmp_path)
    started_at = datetime.utcnow() - timedelta(seconds=90)
    completed_at = datetime.utcnow()
    with Session() as db:
        db.add(
            Job(
                id="job-1",
                source_type="youtube_url",
                source_path="https://youtube.com/watch?v=test",
                source_duration_seconds=120,
                status="done",
                progress=100,
                stage_metrics_json='{"downloading": 12.5, "transcribing": 30.0}',
                processing_started_at=started_at,
                completed_at=completed_at,
            )
        )
        db.commit()

        response = await system.get_performance_baseline(limit=10, db=db)

    assert response["jobs_analyzed"] == 1
    assert response["total_processing_seconds"]["count"] == 1
    assert response["source_duration_seconds"]["avg"] == 120
    assert response["stage_seconds"]["downloading"]["avg"] == 12.5
    assert response["latest_jobs"][0]["id"] == "job-1"


@pytest.mark.asyncio
async def test_release_info_contract(monkeypatch):
    monkeypatch.setattr(system.settings, "app_version", "1.0.0")

    response = await system.get_release_info()

    assert response["name"] == "ClipGen"
    assert response["version"] == "1.0.0"
    assert response["release_channel"] == "local-mvp"
    assert response["features"]["vertical_crop"] is True
    assert response["features"]["youtube_manual_options"] is True
    assert response["features"]["upload_subtitles"] is False
    assert response["features"]["youtube_subtitles"] is True
    assert response["known_risks"]
