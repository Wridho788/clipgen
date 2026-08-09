from app.schemas import JobProcessingOptions
from app.services.processing_estimator import build_stage_estimates, total_estimate_seconds


def test_upload_estimate_skips_download_subtitle_and_crop():
    options = JobProcessingOptions(min_clip_seconds=15, max_clip_seconds=45, clip_count=3)

    estimates = build_stage_estimates(180, "upload", options)

    assert "downloading" not in estimates
    assert "subtitling" not in estimates
    assert "cropping" not in estimates
    assert estimates["transcribing"] > estimates["extracting"]


def test_youtube_manual_estimate_has_download_and_subtitle_when_enabled():
    options = JobProcessingOptions(
        min_clip_seconds=15,
        max_clip_seconds=45,
        clip_count=3,
        generate_subtitles=True,
    )

    estimates = build_stage_estimates(180, "youtube_url", options)

    assert estimates["downloading"] > 0
    assert estimates["subtitling"] > 0
    assert total_estimate_seconds(estimates) == round(sum(estimates.values()), 1)


def test_youtube_automatic_estimate_includes_multi_clip_detection_and_skips_subtitle():
    options = JobProcessingOptions(
        min_clip_seconds=15,
        max_clip_seconds=45,
        clip_count=3,
        processing_mode="automatic",
    )

    estimates = build_stage_estimates(180, "youtube_url", options)

    assert "downloading" in estimates
    assert "cutting" in estimates
    assert "generating_metadata" in estimates
    assert "extracting" in estimates
    assert "transcribing" in estimates
    assert "detecting" in estimates
    assert "subtitling" not in estimates
