import os
from datetime import datetime, timedelta

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
