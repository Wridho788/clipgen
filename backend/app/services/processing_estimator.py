"""Shared, explainable ETA heuristics for upload and job progress screens."""
from typing import Any


STAGE_ORDER = (
    "downloading",
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
    clip_count = max(1, int(options.clip_count)) if options.generate_highlights else 1
    average_clip_duration = (float(options.min_clip_seconds) + float(options.max_clip_seconds)) / 2
    needs_transcript = bool(options.generate_highlights or options.generate_subtitles)

    estimates = {}
    if source_type == "youtube_url":
        estimates["downloading"] = max(45.0, duration * 0.18)
    if needs_transcript:
        estimates["extracting"] = max(4.0, duration * 0.06)
        estimates["transcribing"] = max(20.0, duration * 0.75)
    if options.generate_highlights:
        estimates["detecting"] = max(5.0, duration * 0.06)
    estimates["cutting"] = max(8.0, clip_count * average_clip_duration * 0.65)
    if options.crop_vertical:
        estimates["cropping"] = max(8.0, clip_count * average_clip_duration * 0.55)
    if options.generate_subtitles:
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
