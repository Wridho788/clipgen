import pytest
from fastapi import HTTPException

from app.api.routes.videos import _processing_options_from_form
from app.schemas import JobProcessingOptions


def test_processing_options_accept_custom_values():
    options = _processing_options_from_form(20, 45, 3, "en")

    assert options.min_clip_seconds == 20
    assert options.max_clip_seconds == 45
    assert options.clip_count == 3
    assert options.metadata_language == "en"
    assert options.processing_mode == "manual"
    assert options.generate_highlights is True
    assert options.generate_subtitles is False


def test_processing_options_reject_invalid_duration_range():
    with pytest.raises(HTTPException) as error:
        _processing_options_from_form(60, 15, 3)

    assert error.value.status_code == 422


def test_processing_options_enforce_clip_count_limit():
    with pytest.raises(ValueError, match="less than or equal to 12"):
        JobProcessingOptions(min_clip_seconds=15, max_clip_seconds=30, clip_count=13)


def test_automatic_processing_options_force_safe_youtube_defaults():
    options = _processing_options_from_form(
        15,
        30,
        3,
        "id",
        "automatic",
        True,
        True,
        False,
        True,
    )

    assert options.processing_mode == "automatic"
    assert options.crop_vertical is False
    assert options.generate_highlights is True
    # Automatic mode selects highlights but honors feature choices instead of
    # silently rendering metadata/subtitles that the user disabled.
    assert options.generate_metadata is False
    assert options.generate_subtitles is True
    assert options.clip_count == 3


def test_processing_options_accept_adaptive_clip_count():
    options = JobProcessingOptions(min_clip_seconds=10, max_clip_seconds=60, clip_count=0)

    assert options.clip_count == 0
    assert options.min_clip_seconds == 10


def test_processing_options_map_legacy_crop_and_clean_hook():
    options = JobProcessingOptions(
        min_clip_seconds=15,
        max_clip_seconds=30,
        clip_count=3,
        crop_vertical=True,
        hook_text="  Jangan skip bagian ini  ",
    )

    assert options.output_preset == "tiktok"
    assert options.visual_style == "crop"
    assert options.hook_text == "Jangan skip bagian ini"
