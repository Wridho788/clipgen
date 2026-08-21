import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Clip, ClipFeedback, Job, User
from app.services import maintenance


def test_cleanup_removes_only_old_temp_and_intermediate_files(monkeypatch, tmp_path):
    temp_dir = tmp_path / "temp"
    clips_dir = tmp_path / "clips"
    temp_dir.mkdir()
    clips_dir.mkdir()

    old_temp = temp_dir / "old.wav"
    old_raw = clips_dir / "clip_raw.mp4"
    final_clip = clips_dir / "clip_final.mp4"
    recent_temp = temp_dir / "recent.wav"
    for path in (old_temp, old_raw, final_clip, recent_temp):
        path.write_bytes(b"data")

    old_timestamp = (datetime.utcnow() - timedelta(hours=2)).timestamp()
    os.utime(old_temp, (old_timestamp, old_timestamp))
    os.utime(old_raw, (old_timestamp, old_timestamp))

    monkeypatch.setattr(maintenance.settings, "temp_dir", temp_dir)
    monkeypatch.setattr(maintenance.settings, "clips_dir", clips_dir)
    monkeypatch.setattr(maintenance.settings, "temp_cleanup_enabled", True)
    monkeypatch.setattr(maintenance.settings, "temp_file_retention_hours", 1)

    report = maintenance.cleanup_temporary_files()

    assert report.files_deleted == 2
    assert not old_temp.exists()
    assert not old_raw.exists()
    assert final_clip.exists()
    assert recent_temp.exists()


def _storage_session(database_path):
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_clear_workspace_moves_assets_and_database_snapshot_to_recycle(monkeypatch, tmp_path):
    storage_dir = tmp_path / "storage"
    upload_dir = storage_dir / "uploads"
    clips_dir = storage_dir / "clips"
    temp_dir = storage_dir / "temp"
    for directory in (upload_dir, clips_dir, temp_dir):
        directory.mkdir(parents=True)
    source = upload_dir / "source.mp4"
    source_info = upload_dir / "source.info.json"
    clip_file = clips_dir / "clip.mp4"
    temp_file = temp_dir / "audio.wav"
    for path in (source, source_info, clip_file, temp_file):
        path.write_bytes(b"data")

    database_path = storage_dir / "app.db"
    Session = _storage_session(database_path)
    monkeypatch.setattr(maintenance.settings, "storage_dir", storage_dir)
    monkeypatch.setattr(maintenance.settings, "temp_dir", temp_dir)
    monkeypatch.setattr(maintenance.settings, "database_url", f"sqlite:///{database_path}")

    with Session() as db:
        db.add(User(id="user-1", username="tester", display_name="Tester"))
        db.add(Job(id="job-1", owner_id="user-1", source_type="upload", source_path=str(source), status="done"))
        db.add(Clip(id="clip-1", job_id="job-1", start_time=0, end_time=10, highlight_score=1, file_path=str(clip_file), status="ready"))
        db.add(ClipFeedback(clip_id="clip-1", user_id="user-1", rating=1))
        db.commit()

        report = maintenance.clear_workspace_storage(db, "user-1", "recycle")

        assert report.mode == "recycle"
        assert report.files_handled == 4
        assert report.jobs_deleted == 1
        assert report.clips_deleted == 1
        assert report.recycle_path
        recycle_path = Path(report.recycle_path)
        assert (recycle_path / "uploads" / "source.mp4").exists()
        assert (recycle_path / "uploads" / "source.info.json").exists()
        assert (recycle_path / "clips" / "clip.mp4").exists()
        assert (recycle_path / "temp" / "audio.wav").exists()
        assert (recycle_path / "app-before-clear.db").exists()
        assert db.query(Job).count() == 0
        assert db.query(Clip).count() == 0
        assert db.query(ClipFeedback).count() == 0


def test_clear_workspace_permanent_removes_old_recycle_content(monkeypatch, tmp_path):
    storage_dir = tmp_path / "storage"
    upload_dir = storage_dir / "uploads"
    temp_dir = storage_dir / "temp"
    recycle_dir = storage_dir / ".recycle-bin" / "old"
    for directory in (upload_dir, temp_dir, recycle_dir):
        directory.mkdir(parents=True)
    source = upload_dir / "source.mp4"
    temp_file = temp_dir / "audio.wav"
    old_recycled = recycle_dir / "old.mp4"
    for path in (source, temp_file, old_recycled):
        path.write_bytes(b"data")

    database_path = storage_dir / "app.db"
    Session = _storage_session(database_path)
    monkeypatch.setattr(maintenance.settings, "storage_dir", storage_dir)
    monkeypatch.setattr(maintenance.settings, "temp_dir", temp_dir)
    monkeypatch.setattr(maintenance.settings, "database_url", f"sqlite:///{database_path}")

    with Session() as db:
        db.add(User(id="user-1", username="tester", display_name="Tester"))
        db.add(Job(id="job-1", owner_id="user-1", source_type="upload", source_path=str(source), status="done"))
        db.commit()

        report = maintenance.clear_workspace_storage(db, "user-1", "permanent")

        assert report.mode == "permanent"
        assert report.files_handled == 3
        assert report.bytes_reclaimed == 12
        assert not source.exists()
        assert not temp_file.exists()
        assert not old_recycled.exists()
        assert db.query(Job).count() == 0


def test_clear_workspace_blocks_active_job(monkeypatch, tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    database_path = storage_dir / "app.db"
    Session = _storage_session(database_path)
    monkeypatch.setattr(maintenance.settings, "storage_dir", storage_dir)
    monkeypatch.setattr(maintenance.settings, "temp_dir", storage_dir / "temp")
    monkeypatch.setattr(maintenance.settings, "database_url", f"sqlite:///{database_path}")

    with Session() as db:
        db.add(User(id="user-1", username="tester", display_name="Tester"))
        db.add(Job(id="job-1", owner_id="user-1", source_type="upload", source_path="video.mp4", status="transcribing"))
        db.commit()

        with pytest.raises(maintenance.StorageBusyError):
            maintenance.clear_workspace_storage(db, "user-1", "recycle")
