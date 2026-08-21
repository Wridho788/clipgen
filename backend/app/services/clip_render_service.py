"""Queued re-rendering for user-adjusted clip ranges."""
import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from app.config import settings
from app.core.pipeline.clip_cut import cut_clip
from app.core.pipeline.subtitle_burn import burn_subtitles
from app.core.pipeline.transcribe import Segment, Word
from app.core.pipeline.social_render import render_social_clip
from app.database import SessionLocal
from app.models import Clip, Job
from app.schemas import JobProcessingOptions, default_processing_options
from app.services.job_dispatcher import enqueue_task


async def enqueue_clip_trim(clip_id: str) -> None:
    def render() -> None:
        render_trimmed_clip(clip_id)

    await enqueue_task(f"clip-trim:{clip_id}", render)


def render_trimmed_clip(clip_id: str) -> None:
    """Replace a ready clip with a new range while retaining its metadata."""
    with SessionLocal() as db:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if clip is None:
            return
        job = db.query(Job).filter(Job.id == clip.job_id).first()
        if job is None or not Path(job.source_path).exists():
            clip.status = "failed"
            db.commit()
            return

        old_path = Path(clip.file_path) if clip.file_path else None
        try:
            options = _processing_options(job.processing_options)
            needs_social_render = (
                options.output_preset != "original" or options.visual_style != "clean"
            )
            if needs_social_render:
                final_path = render_social_clip(
                    Path(job.source_path),
                    settings.clips_dir,
                    clip.id,
                    output_preset=options.output_preset,
                    visual_style=options.visual_style,
                    start_time=clip.start_time,
                    end_time=clip.end_time,
                )
            else:
                final_path = cut_clip(
                    Path(job.source_path),
                    clip.start_time,
                    clip.end_time,
                    settings.clips_dir,
                    clip.id,
                )
            if options.generate_subtitles:
                final_path = burn_subtitles(
                    final_path,
                    _segments(job.transcript_json),
                    clip.id,
                    settings.clips_dir,
                    clip_start_time=clip.start_time,
                )

            clip.file_path = str(final_path)
            clip.status = "ready"
            job.updated_at = datetime.utcnow()
            db.commit()
            if old_path and old_path != final_path:
                old_path.unlink(missing_ok=True)
            logger.info(f"Trimmed clip {clip_id} rendered")
        except Exception as error:
            clip.status = "failed"
            db.commit()
            logger.error(f"Clip trim failed for {clip_id}: {error}", exc_info=True)


def _processing_options(raw_value: str | None) -> JobProcessingOptions:
    try:
        stored = json.loads(raw_value or "{}")
    except json.JSONDecodeError:
        stored = {}
    return JobProcessingOptions.model_validate({**default_processing_options().model_dump(), **stored})


def _segments(raw_value: str | None) -> list[Segment]:
    try:
        data = json.loads(raw_value or "[]")
    except json.JSONDecodeError:
        return []
    result = []
    for item in data if isinstance(data, list) else []:
        try:
            words = [
                Word(float(word["start"]), float(word["end"]), str(word["text"]))
                for word in item.get("words", [])
                if isinstance(word, dict)
                and "start" in word
                and "end" in word
                and "text" in word
            ]
            result.append(
                Segment(float(item["start"]), float(item["end"]), str(item["text"]), words)
            )
        except (KeyError, TypeError, ValueError):
            continue
    return result
