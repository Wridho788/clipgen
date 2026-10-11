"""Shared, explainable ETA heuristics for upload and job progress screens."""
from typing import Any

from app.config import settings
from app.services.clip_planning import resolve_clip_count
from app.services.runtime_capabilities import get_runtime_capabilities


# Seconds of CPU transcription per second of audio (int8, beam 3, 4 threads),
# measured on this project's dev machine (docs/09 §2, §4.1). Clean speech is
# faster, noisy TV audio slower; the live throughput projection replaces this
# preflight value once a job has transcribed ~5% of its audio.
MODEL_CPU_TRANSCRIPTION_RTF: dict[str, float] = {
    "tiny": 1.75,
    "base": 3.0,
    "small": 4.8,
    "medium": 11.0,
}


def cpu_transcription_rtf(model_size: str | None = None) -> float:
    if settings.cpu_transcription_rtf is not None:
        return settings.cpu_transcription_rtf
    model = (model_size or settings.whisper_model_size or "").lower()
    return MODEL_CPU_TRANSCRIPTION_RTF.get(model, MODEL_CPU_TRANSCRIPTION_RTF["small"])


STAGE_ORDER = (
    "downloading",
    "extracting",
    "transcribing",
    "cutting",
    "cropping",
    "generating_metadata",
)


def build_stage_estimates(
    duration_seconds: float | None,
    source_type: str,
    options: Any,
) -> dict[str, float]:
    """Estimate the same stages the worker exposes; values are deliberately conservative."""
    duration = max(30.0, float(duration_seconds or 600.0))
    clip_count = resolve_clip_count(duration, int(options.clip_count))
    average_clip_duration = (float(options.min_clip_seconds) + float(options.max_clip_seconds)) / 2
    # Mirrors JobService._needs_transcript: captions need a transcript too.
    needs_transcript = bool(options.generate_metadata or getattr(options, "burn_captions", False))
    needs_social_render = bool(
        options.output_preset != "original" or options.visual_style != "clean"
    )

    estimates = {}
    if source_type == "youtube_url":
        estimates["downloading"] = max(45.0, duration * 0.18)
    capabilities = get_runtime_capabilities()
    if needs_transcript:
        estimates["extracting"] = max(4.0, duration * 0.06)
        transcription_rtf = (
            settings.gpu_transcription_rtf
            if capabilities.transcription_device == "cuda"
            else cpu_transcription_rtf()
        )
        estimates["transcribing"] = max(20.0, duration * transcription_rtf)
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
    if options.generate_metadata:
        estimates["generating_metadata"] = max(8.0, clip_count * 10.0)

    return {
        stage: round(estimate, 1)
        for stage, estimate in estimates.items()
        if estimate > 0
    }


def total_estimate_seconds(stage_estimates: dict[str, float]) -> float:
    return round(sum(stage_estimates.values()), 1)
