from app.schemas import JobProcessingOptions
from app.services.processing_estimator import build_stage_estimates, total_estimate_seconds


def test_upload_estimate_skips_download_subtitle_and_crop():
    options = JobProcessingOptions(min_clip_seconds=15, max_clip_seconds=45, clip_count=3)

    estimates = build_stage_estimates(180, "upload", options)

    assert "downloading" not in estimates
    assert "subtitling" not in estimates
    assert "cropping" not in estimates
    assert estimates["transcribing"] > estimates["extracting"]


def test_youtube_manual_estimate_has_download_without_text_overlays():
    options = JobProcessingOptions(
        min_clip_seconds=15,
        max_clip_seconds=45,
        clip_count=3,
    )

    estimates = build_stage_estimates(180, "youtube_url", options)

    assert estimates["downloading"] > 0
    assert "subtitling" not in estimates
    assert total_estimate_seconds(estimates) == round(sum(estimates.values()), 1)


def test_youtube_automatic_estimate_has_clip_render_without_detection_or_subtitles():
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
    assert "detecting" not in estimates
    assert "subtitling" not in estimates


def test_transcription_estimate_follows_model_size(monkeypatch):
    from app.services import processing_estimator

    monkeypatch.setattr(processing_estimator.settings, "cpu_transcription_rtf", None)
    monkeypatch.setattr(
        processing_estimator,
        "get_runtime_capabilities",
        lambda: type("Caps", (), {"transcription_device": "cpu", "render_device": "cpu"})(),
    )
    options = JobProcessingOptions(min_clip_seconds=15, max_clip_seconds=45, clip_count=1)
    by_model = {}
    for model in ("tiny", "small"):
        monkeypatch.setattr(processing_estimator.settings, "whisper_model_size", model)
        by_model[model] = build_stage_estimates(600, "upload", options)["transcribing"]
    assert by_model["tiny"] == 600 * 1.75
    assert by_model["small"] == 600 * 4.8
    # An explicit override still wins.
    monkeypatch.setattr(processing_estimator.settings, "cpu_transcription_rtf", 2.0)
    assert build_stage_estimates(600, "upload", options)["transcribing"] == 1200


def test_captions_alone_still_budget_transcription():
    options = JobProcessingOptions(
        min_clip_seconds=15, max_clip_seconds=45, clip_count=1, generate_metadata=False, burn_captions=True
    )
    assert "transcribing" in build_stage_estimates(300, "upload", options)
    no_text = options.model_copy(update={"burn_captions": False})
    assert "transcribing" not in build_stage_estimates(300, "upload", no_text)
