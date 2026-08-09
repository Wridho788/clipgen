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
    with pytest.raises(ValueError, match="less than or equal to 10"):
        JobProcessingOptions(min_clip_seconds=15, max_clip_seconds=30, clip_count=11)


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
    assert options.generate_metadata is True
    assert options.generate_subtitles is False
    assert options.clip_count >= 3
