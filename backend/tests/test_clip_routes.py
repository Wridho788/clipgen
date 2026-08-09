import json
import zipfile

from app.api.routes.clips import _build_job_archive, _get_clip_transcript_text, _safe_download_filename
from app.models import Clip, Job


def test_safe_download_filename_strips_unsafe_characters():
    assert _safe_download_filename("A/B: C?") == "A_B_C"


def test_safe_download_filename_falls_back_to_clip():
    assert _safe_download_filename("///") == "clip"


def test_get_clip_transcript_text_returns_overlapping_segments():
    job = Job(
        id="job-1",
        source_type="upload",
        source_path="/tmp/source.mp4",
        transcript_json=json.dumps(
            [
                {"start": 1, "end": 4, "text": "before"},
                {"start": 4, "end": 8, "text": "inside"},
                {"start": 10, "end": 12, "text": "after"},
            ]
        ),
    )
    clip = Clip(
        id="clip-1",
        job_id="job-1",
        start_time=3,
        end_time=9,
        highlight_score=1,
    )

    assert _get_clip_transcript_text(job, clip) == "before inside"


def test_build_job_archive_uses_safe_unique_filenames(tmp_path):
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"video")
    archive_path = tmp_path / "clips.zip"
    clip = Clip(
        id="clip-12345678",
        job_id="job-1",
        start_time=0,
        end_time=10,
        highlight_score=1,
        file_path=str(clip_path),
        title="A/B: C?",
        status="ready",
    )

    _build_job_archive(archive_path, [clip])

    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == ["01-A_B_C-clip-123.mp4"]
