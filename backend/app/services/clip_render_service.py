"""
Render a clip's saved edit into a validated MP4 (docs/02 §9-10, docs/05 §4-5).

Flow for every render (initial job render and user re-renders alike):
  1. snapshot the saved ``ClipEdit`` and its revision;
  2. build the FFmpeg plan + ASS captions from that snapshot only;
  3. render into ``temp/`` under a ``.partial`` name;
  4. probe/decode-validate the output;
  5. atomically move it into ``clips/`` and only then point the clip at it.

A failure at any step leaves the previous file (if any) in place, keeps the
edit untouched, and records ``render_error_code``/``render_error_message`` so
the user can retry.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from loguru import logger

from app.config import settings
from app.core.edit_model import ClipEdit
from app.core.errors import ErrorCode, PipelineError, describe_failure
from app.core.pipeline.render_plan import SourceFacts, build_render_plan
from app.core.pipeline.social_render import _append_watermark, run_ffmpeg_with_fallback, select_video_encoder
from app.core.timeline import ms_to_seconds, seconds_to_ms
from app.database import SessionLocal
from app.models import Clip, Job
from app.services.clip_editing import job_options, load_edit
from app.services.export_validation import validate_export
from app.services.media_probe import MediaFacts, probe_media


@dataclass(frozen=True)
class RenderOutcome:
    path: Path
    report: dict


def render_edit_to_file(
    *,
    source_path: Path,
    source: MediaFacts,
    edit: ClipEdit,
    clip_id: str,
    revision: int,
    acceleration: str = "auto",
    on_heartbeat: Callable[[], None] | None = None,
    heartbeat_seconds: float = 30.0,
) -> RenderOutcome:
    """Render, validate, and atomically publish one edit revision."""
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    settings.clips_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:8]
    partial_path = settings.temp_dir / f"{clip_id}.r{revision}.{token}.partial.mp4"
    ass_path = settings.temp_dir / f"{clip_id}.r{revision}.{token}.ass"
    final_path = settings.clips_dir / f"{clip_id}_r{revision}.mp4"

    facts = SourceFacts(
        width=source.width,
        height=source.height,
        duration_ms=seconds_to_ms(source.duration_seconds) or None,
        has_audio=source.has_audio,
    )
    encoder = select_video_encoder(acceleration)
    # Width/height are only known after planning, so plan once to size the
    # watermark, then re-plan with it (pure and cheap).
    plan = build_render_plan(
        source_path=source_path, edit=edit, source=facts, output_path=partial_path,
        encoder=encoder, ass_path=None, watermark_filter=None,
    )
    watermark_filter = _watermark_filter(edit, plan.width, plan.height)
    plan = build_render_plan(
        source_path=source_path, edit=edit, source=facts, output_path=partial_path,
        encoder=encoder, ass_path=ass_path if plan.ass_document else None,
        watermark_filter=watermark_filter,
    )
    started = time.perf_counter()
    try:
        if plan.ass_document:
            ass_path.write_text(plan.ass_document, encoding="utf-8")
        result = run_ffmpeg_with_fallback(
            plan.command, encoder, on_heartbeat=on_heartbeat, heartbeat_seconds=heartbeat_seconds,
        )
        if result.returncode != 0:
            raise PipelineError(ErrorCode.EXPORT_FAILED, result.stderr[-600:] or f"exit {result.returncode}")
        validation = validate_export(
            partial_path,
            expected_width=plan.width,
            expected_height=plan.height,
            expected_duration_seconds=ms_to_seconds(plan.duration_ms),
            expects_audio=plan.expects_audio,
        )
        if not validation.ok:
            raise PipelineError(ErrorCode.EXPORT_VALIDATION_FAILED, "; ".join(validation.problems))
        os.replace(partial_path, final_path)
    finally:
        partial_path.unlink(missing_ok=True)
        ass_path.unlink(missing_ok=True)

    elapsed = round(time.perf_counter() - started, 2)
    report = {
        "revision": revision,
        "rendered_at": datetime.utcnow().isoformat() + "Z",
        "render_seconds": elapsed,
        "encoder": encoder,
        "captions_rendered": len(edit.rendered_cues()),
        "validation": validation.as_dict(),
    }
    logger.info(
        f"Clip {clip_id} r{revision} rendered in {elapsed}s "
        f"({plan.width}x{plan.height}, {ms_to_seconds(plan.duration_ms)}s, encoder={encoder})"
    )
    return RenderOutcome(path=final_path, report=report)


def apply_render_success(clip: Clip, outcome: RenderOutcome, revision: int) -> Path | None:
    """Point the clip at the new file; return the superseded file to delete."""
    previous = Path(clip.file_path) if clip.file_path else None
    clip.file_path = str(outcome.path)
    clip.rendered_revision = revision
    clip.status = "ready"
    clip.render_error_code = None
    clip.render_error_message = None
    clip.render_report_json = json.dumps(outcome.report)
    clip.updated_at = datetime.utcnow()
    return previous if previous and previous != outcome.path else None


def apply_render_failure(clip: Clip, error: BaseException) -> None:
    code, message = describe_failure(error)
    if code not in {ErrorCode.EXPORT_VALIDATION_FAILED, ErrorCode.SOURCE_MISSING, ErrorCode.INTERRUPTED}:
        code = ErrorCode.EXPORT_FAILED if code == ErrorCode.UNKNOWN else code
    has_previous = bool(clip.file_path) and Path(clip.file_path).exists()
    clip.status = "ready" if has_previous else "failed"
    clip.render_error_code = code.value
    clip.render_error_message = message
    clip.updated_at = datetime.utcnow()


async def enqueue_clip_render(clip_id: str) -> None:
    # Imported lazily: job_dispatcher imports job_service, which imports this module.
    from app.services.job_dispatcher import enqueue_task

    def render() -> None:
        render_saved_edit(clip_id)

    await enqueue_task(f"clip-render:{clip_id}:{uuid.uuid4().hex[:6]}", render)


# Backwards-compatible name used by the trim route and older tests.
enqueue_clip_trim = enqueue_clip_render


def render_saved_edit(clip_id: str) -> None:
    """Worker entry point: render whatever edit revision is saved right now."""
    with SessionLocal() as db:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if clip is None:
            return
        job = db.query(Job).filter(Job.id == clip.job_id).first()
        revision = int(clip.edit_revision or 0)
        try:
            if job is None or not Path(job.source_path).exists():
                raise PipelineError(ErrorCode.SOURCE_MISSING)
            source = probe_media(Path(job.source_path))
            if source is None:
                raise PipelineError(ErrorCode.SOURCE_CORRUPT)
            edit = load_edit(clip, job)
            options = job_options(job)
            outcome = render_edit_to_file(
                source_path=Path(job.source_path),
                source=source,
                edit=edit,
                clip_id=clip.id,
                revision=revision,
                acceleration=options.render_acceleration,
            )
        except Exception as error:
            db.rollback()
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if clip is None:
                return
            apply_render_failure(clip, error)
            db.commit()
            logger.error(f"Clip render failed for {clip_id}: {error}")
            return

        db.refresh(clip)
        superseded = apply_render_success(clip, outcome, revision)
        if job is not None:
            job.updated_at = datetime.utcnow()
        db.commit()
        if superseded is not None:
            superseded.unlink(missing_ok=True)


# Older imports.
render_trimmed_clip = render_saved_edit


def _watermark_filter(edit: ClipEdit, width: int, height: int) -> str | None:
    if not edit.watermark_enabled or not settings.watermark_enabled or not settings.watermark_text:
        return None
    return _append_watermark("null", settings.watermark_text, None, None, width, height).removeprefix("null,")
