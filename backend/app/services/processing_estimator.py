"""Shared, explainable ETA heuristics for upload and job progress screens."""
from typing import Any

from app.config import settings
from app.services.clip_planning import resolve_clip_count
from app.services.runtime_capabilities import get_runtime_capabilities


STAGE_ORDER = (
    "downloading",
    "analyzing_intro",
    "extracting",
    "transcribing",
    "detecting",
    "cutting",
    "cropping",
    "subtitling",
    "generating_metadata",
)


def build_stage_estimates(
    duration_seconds: float | None,
    source_type: str,
    options: Any,
) -> dict[str, float]:
    """Estimate the same stages the worker exposes; values are deliberately conservative."""
    duration = max(30.0, float(duration_seconds or 600.0))
    clip_count = (
        resolve_clip_count(duration, int(options.clip_count))
        if options.generate_highlights
        else 1
    )
    average_clip_duration = (float(options.min_clip_seconds) + float(options.max_clip_seconds)) / 2
    needs_transcript = bool(
        options.generate_highlights or options.generate_subtitles or options.generate_metadata
    )
    needs_social_render = bool(
        options.output_preset != "original" or options.visual_style != "clean"
    )
    needs_text_overlay = bool(options.generate_subtitles or options.hook_text)

    estimates = {}
    if source_type == "youtube_url":
        estimates["downloading"] = max(45.0, duration * 0.18)
    if (
        source_type == "youtube_url"
        and options.processing_mode == "automatic"
        and options.generate_highlights
    ):
        estimates["analyzing_intro"] = max(4.0, min(15.0, duration * 0.01))
    capabilities = get_runtime_capabilities()
    if needs_transcript:
        estimates["extracting"] = max(4.0, duration * 0.06)
        transcription_rtf = (
            settings.gpu_transcription_rtf
            if capabilities.transcription_device == "cuda"
            else settings.cpu_transcription_rtf
        )
        # Word-level alignment is useful for karaoke, but costs more than the
        # segment timestamps needed by contextual clipping alone.
        if options.generate_subtitles:
            transcription_rtf *= 1.2
        estimates["transcribing"] = max(20.0, duration * transcription_rtf)
    if options.generate_highlights:
        estimates["detecting"] = max(5.0, duration * 0.06)
    if needs_social_render:
        # One direct source→social render includes trimming and reframing. CPU
        # blur is intentionally budgeted conservatively until live throughput
        # replaces this preflight estimate.
        render_factor = 0.7 if capabilities.render_device == "gpu" else (
            2.8 if options.visual_style == "blur" else 1.4
        )
        estimates["cropping"] = max(8.0, clip_count * average_clip_duration * render_factor)
    else:
        cut_factor = 0.3 if capabilities.render_device == "gpu" else 1.2
        estimates["cutting"] = max(8.0, clip_count * average_clip_duration * cut_factor)
    if needs_text_overlay:
        estimates["subtitling"] = max(8.0, clip_count * average_clip_duration * 0.45)
    if options.generate_metadata:
        estimates["generating_metadata"] = max(8.0, clip_count * 10.0)

    return {
        stage: round(estimate, 1)
        for stage, estimate in estimates.items()
        if estimate > 0
    }


def total_estimate_seconds(stage_estimates: dict[str, float]) -> float:
    return round(sum(stage_estimates.values()), 1)
