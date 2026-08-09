from pathlib import Path

from app.core.pipeline.subtitle_burn import _escape_filter_path, _seconds_to_srt_time


def test_seconds_to_srt_time_uses_srt_comma_separator():
    assert _seconds_to_srt_time(65.4321) == "00:01:05,432"


def test_seconds_to_srt_time_clamps_negative_values():
    assert _seconds_to_srt_time(-1) == "00:00:00,000"


def test_escape_filter_path_handles_windows_drive_colon():
    escaped = _escape_filter_path(Path("C:/tmp/my clip/subs.srt"))
    assert escaped == "C\\:/tmp/my clip/subs.srt"
