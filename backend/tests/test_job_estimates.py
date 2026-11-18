from datetime import datetime, timedelta

from app.models import Job


def test_overall_eta_keeps_future_stages_after_slow_transcription():
    job = Job(
        source_type="upload",
        source_path="/tmp/source.mp4",
        status="transcribing",
        stage_estimates_json=(
            '{"extracting": 5, "transcribing": 60, '
            '"cutting": 30, "generating_metadata": 15}'
        ),
        stage_metrics_json='{"extracting": 5}',
        stage_started_at=datetime.utcnow() - timedelta(seconds=120),
    )

    assert job.current_stage_eta_seconds >= 60
    assert job.overall_eta_seconds >= 105


def test_youtube_eta_uses_only_active_processing_stages():
    job = Job(
        source_type="youtube_url",
        source_path="https://youtu.be/example",
        status="pending",
        stage_estimates_json='{"downloading": 45, "extracting": 5}',
    )

    assert job.estimated_total_seconds == 50
    assert job.overall_eta_seconds == 50
