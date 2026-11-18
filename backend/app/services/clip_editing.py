"""
Clip edit persistence and candidate review transitions.

Every user-visible edit goes through ``save_edit`` so the stored ``ClipEdit``
stays the single source of truth for preview and export. Saves use optimistic
concurrency: the caller sends the revision it edited, and a stale revision is
rejected instead of silently overwriting newer work (docs/03 §11).
"""
from __future__ import annotations

import json
from datetime import datetime

from pydantic import ValidationError

from app.config import settings
from app.core.edit_model import ClipEdit, default_edit, build_caption_cues
from app.core.errors import ErrorCode, PipelineError
from app.core.timeline import ms_to_seconds, normalize_segments, seconds_to_ms
from app.models import Clip, Job
from app.schemas import JobProcessingOptions, default_processing_options

REVIEW_STATUSES = ("suggested", "accepted", "rejected", "edited", "exported")
REJECTION_REASONS = (
    "context_missing",
    "weak_moment",
    "bad_boundaries",
    "transcript_error",
    "repeated_content",
    "poor_crop",
    "other",
)


def job_options(job: Job | None) -> JobProcessingOptions:
    defaults = default_processing_options().model_dump()
    try:
        stored = json.loads(job.processing_options or "{}") if job else {}
        if not isinstance(stored, dict):
            stored = {}
    except json.JSONDecodeError:
        stored = {}
    allowed = {key: value for key, value in stored.items() if key in defaults}
    try:
        return JobProcessingOptions.model_validate({**defaults, **allowed})
    except ValidationError:
        return JobProcessingOptions.model_validate(defaults)


def watermark_default(options: JobProcessingOptions) -> bool:
    return options.processing_mode != "automatic"


def load_edit(clip: Clip, job: Job | None) -> ClipEdit:
    """Return the stored edit, or derive one for clips created before v2."""
    if clip.edit_json:
        try:
            return ClipEdit.model_validate_json(clip.edit_json)
        except ValidationError:
            pass
    options = job_options(job)
    start_ms = seconds_to_ms(clip.start_time)
    end_ms = max(start_ms + 1, seconds_to_ms(clip.end_time))
    # Cues are prepared so the user can switch captions on, but they start
    # disabled: files rendered before v2 never contained burned captions, and
    # the derived edit must describe what the existing file actually shows.
    cues = build_caption_cues(transcript_segments(job), start_ms, end_ms) if job is not None else []
    try:
        edit = default_edit(
            start_ms=start_ms,
            end_ms=end_ms,
            output_preset=options.output_preset,
            visual_style=options.visual_style,
            captions_enabled=False,
            cues=cues,
            watermark_enabled=watermark_default(options),
        )
        return edit
    except ValidationError:
        # Legacy clips may be shorter than today's minimum; widen the stored
        # document only, the existing file is untouched until a re-render.
        return default_edit(
            start_ms=start_ms,
            end_ms=start_ms + 5_000,
            output_preset=options.output_preset,
            visual_style=options.visual_style,
            captions_enabled=False,
            watermark_enabled=watermark_default(options),
        )


def transcript_segments(job: Job):
    try:
        raw = json.loads(job.transcript_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    try:
        segments, _ = normalize_segments(raw, seconds_to_ms(job.source_duration_seconds) or None)
    except PipelineError:
        return []
    return segments


def store_edit(clip: Clip, edit: ClipEdit) -> None:
    clip.edit_json = edit.model_dump_json()
    clip.start_time = ms_to_seconds(edit.trim_start_ms)
    clip.end_time = ms_to_seconds(edit.trim_end_ms)


def save_edit(clip: Clip, job: Job, edit: ClipEdit, base_revision: int) -> ClipEdit:
    """Validate and persist a user edit; caller commits the session."""
    current_revision = int(clip.edit_revision or 0)
    if base_revision != current_revision:
        raise PipelineError(
            ErrorCode.EDIT_CONFLICT,
            f"revisi {base_revision} sudah usang, revisi terbaru {current_revision}",
        )
    try:
        edit.check_against_source(seconds_to_ms(job.source_duration_seconds) or None)
    except ValueError as error:
        raise PipelineError(ErrorCode.EDIT_INVALID, str(error), message=str(error)) from error
    store_edit(clip, edit)
    clip.edit_revision = current_revision + 1
    if clip.review_status in {"suggested", "accepted", "exported"}:
        clip.review_status = "edited"
    clip.updated_at = datetime.utcnow()
    return edit


def set_review(clip: Clip, status: str, reason: str | None) -> None:
    if status not in {"suggested", "accepted", "rejected"}:
        raise PipelineError(ErrorCode.EDIT_INVALID, f"status review tidak dikenal: {status}")
    if status == "rejected":
        if reason not in REJECTION_REASONS:
            raise PipelineError(
                ErrorCode.EDIT_INVALID,
                message="Pilih alasan penolakan agar kualitas kandidat bisa dievaluasi.",
            )
        clip.review_reason = reason
    else:
        clip.review_reason = None
    clip.review_status = status
    clip.updated_at = datetime.utcnow()


def mark_exported(clip: Clip) -> None:
    clip.exported_at = datetime.utcnow()
    if clip.review_status != "rejected":
        clip.review_status = "exported"


def is_render_stale(clip: Clip) -> bool:
    if clip.rendered_revision is None:
        return bool(clip.edit_revision)
    return int(clip.rendered_revision) < int(clip.edit_revision or 0)


def candidate_payload(clip: Clip) -> dict | None:
    try:
        analysis = json.loads(clip.analysis_json or "null")
    except json.JSONDecodeError:
        analysis = None
    if not isinstance(analysis, dict):
        if not clip.algorithm_version:
            return None
        analysis = {}
    analysis.setdefault("algorithm_version", clip.algorithm_version or "even-spacing-v1")
    analysis.setdefault(
        "score_meaning", "Peringkat relatif di dalam job ini, bukan prediksi views atau viralitas."
    )
    analysis.setdefault("explanation", [])
    analysis.setdefault("signals", {})
    # The raw score is an internal ranking input; expose rank instead.
    analysis.pop("score", None)
    return analysis


def default_settings_watermark_text() -> str | None:
    return settings.watermark_text if settings.watermark_enabled and settings.watermark_text else None
