import pytest

from app.api.routes.videos import estimate_processing_time


@pytest.mark.asyncio
async def test_upload_estimate_contract_skips_youtube_only_stages():
    response = await estimate_processing_time(
        duration_seconds=120,
        source_type="upload",
        min_clip_seconds=None,
        max_clip_seconds=None,
        clip_count=None,
        metadata_language="id",
        processing_mode=None,
        crop_vertical=None,
        generate_highlights=None,
        generate_metadata=None,
        generate_subtitles=None,
        context_aware=None,
        output_preset=None,
        visual_style=None,
        subtitle_style=None,
        hook_text=None,
        render_acceleration=None,
    )

    assert response.source_type == "upload"
    assert response.estimated_processing_seconds > 0
    assert "extracting" in response.stage_estimates
    assert "transcribing" in response.stage_estimates
    assert "generating_metadata" in response.stage_estimates
    assert "downloading" not in response.stage_estimates
    assert "subtitling" not in response.stage_estimates
    assert "cropping" not in response.stage_estimates


@pytest.mark.asyncio
async def test_youtube_estimate_contract_includes_download_and_manual_subtitle():
    response = await estimate_processing_time(
        duration_seconds=120,
        source_type="youtube_url",
        min_clip_seconds=15,
        max_clip_seconds=30,
        clip_count=3,
        metadata_language="en",
        processing_mode="manual",
        crop_vertical=None,
        generate_highlights=None,
        generate_metadata=None,
        generate_subtitles=True,
        context_aware=None,
        output_preset=None,
        visual_style=None,
        subtitle_style=None,
        hook_text=None,
        render_acceleration=None,
    )

    assert response.source_type == "youtube_url"
    assert response.stage_estimates["downloading"] > 0
    assert response.stage_estimates["subtitling"] > 0
    assert response.stage_estimates["generating_metadata"] > 0
    assert "cropping" not in response.stage_estimates


@pytest.mark.asyncio
async def test_youtube_automatic_estimate_includes_multi_clip_detection():
    response = await estimate_processing_time(
        duration_seconds=120,
        source_type="youtube_url",
        min_clip_seconds=15,
        max_clip_seconds=30,
        clip_count=3,
        metadata_language="id",
        processing_mode="automatic",
        crop_vertical=None,
        generate_highlights=None,
        generate_metadata=None,
        generate_subtitles=None,
        context_aware=None,
        output_preset=None,
        visual_style=None,
        subtitle_style=None,
        hook_text=None,
        render_acceleration=None,
    )

    assert response.stage_estimates["downloading"] > 0
    assert response.stage_estimates["cutting"] > 0
    assert response.stage_estimates["generating_metadata"] > 0
    assert "transcribing" in response.stage_estimates
    assert "detecting" in response.stage_estimates
    assert "subtitling" not in response.stage_estimates
