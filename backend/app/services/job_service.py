"""
Job Service — orchestrator yang mengelola job lifecycle.
Ini interface antara API routes dan pipeline stages.

Satu instance JobService handle satu job, call stages satu-satu,
update DB status + progress, handle error per stage.
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.models import Job, Clip
from app.schemas import JobProcessingOptions, default_processing_options
from app.core.pipeline.audio_extract import extract_audio
from app.core.pipeline.transcribe import transcribe
from app.core.edit_model import ClipEdit, build_caption_cues, default_edit
from app.core.errors import ErrorCode, PipelineError, describe_failure
from app.core.pipeline.metadata_gen import generate_metadata
from app.core.timeline import TimedSegment, ms_to_seconds, normalize_segments, seconds_to_ms, segments_to_json
from app.services.candidates import Candidate, generate_candidates
from app.services.clip_editing import watermark_default
from app.services.clip_render_service import apply_render_success, render_edit_to_file
from app.services.media_probe import MediaFacts, probe_media
from app.services.processing_estimator import build_stage_estimates
from app.services.eta_calibration import calibrate_stage_estimates
from app.services.clip_planning import resolve_clip_count
from app.services.youtube_downloader import download_youtube_video
from app.services.youtube_access import require_youtube_access
from app.services.source_metadata import load_youtube_reference_hashtags


class JobCancelled(Exception):
    """Raised internally when a queued/running job has been cancelled."""


@dataclass(frozen=True)
class ClipWindow:
    start: float
    end: float


class JobService:
    """Manage satu job dari start sampai selesai."""

    def __init__(self, job_id: str, db: Session):
        self.job_id = job_id
        self.db = db
        self.job = db.query(Job).filter(Job.id == job_id).first()
        if not self.job:
            raise ValueError(f"Job {job_id} not found")
        self._stage_occurrences: dict[str, int] = {}
        self._planned_stage_occurrences: dict[str, int] = {}

    def _ensure_not_cancelled(self):
        """Refresh job state and stop processing if user cancelled the job."""
        self.db.refresh(self.job)
        if self.job.status == "cancelled":
            raise JobCancelled(f"Job {self.job_id} cancelled")

    def _update_status(
        self,
        status: str,
        progress: int = None,
        error_msg: str = None,
        error_code: str | None = None,
    ):
        """Helper untuk update job status + progress ke DB."""
        self._ensure_not_cancelled()
        now = datetime.utcnow()
        previous_status = self.job.status
        active_stages = {
            "extracting",
            "transcribing",
            "cutting",
            "cropping",
            "downloading",
            "generating_metadata",
        }

        if previous_status in active_stages and previous_status != status:
            self._record_stage_duration(previous_status, now)

        self.job.status = status
        calculated_progress = self._pipeline_progress(status)
        if calculated_progress is not None and status in active_stages:
            self.job.progress = calculated_progress
        elif progress is not None:
            self.job.progress = progress
        if error_msg:
            self.job.error_message = error_msg
        if error_code:
            self.job.error_code = error_code
        if status in active_stages:
            if self.job.processing_started_at is None:
                self.job.processing_started_at = now
            self.job.stage_started_at = now
            self.job.heartbeat_at = now
        elif status in {"done", "failed"}:
            self.job.completed_at = now
            self.job.stage_started_at = None
            self.job.heartbeat_at = now
            if status == "done":
                self.job.error_message = None
                self.job.error_code = None
        self.job.updated_at = now
        self.db.commit()
        logger.info(
            f"Job {self.job_id}: status={status}, progress={self.job.progress}, error={error_msg}"
        )

    def _transcription_timeout_seconds(self) -> int:
        """Scale the hard stop to the job's ETA while retaining sane bounds."""
        estimate = float(self.job.stage_estimates.get("transcribing", 0.0))
        planned = estimate * settings.transcription_timeout_multiplier
        return int(
            min(
                settings.transcription_timeout_max_seconds,
                max(settings.transcription_timeout_min_seconds, planned),
            )
        )

    def _record_transcription_heartbeat(self, processed_seconds: float | None) -> None:
        """Persist liveness and live RTF-based ETA while Whisper streams segments."""
        self._ensure_not_cancelled()
        now = datetime.utcnow()
        last_heartbeat = self.job.heartbeat_at
        heartbeat_age = (
            (now - last_heartbeat).total_seconds()
            if last_heartbeat is not None
            else float("inf")
        )

        duration = float(self.job.source_duration_seconds or 0.0)
        next_progress = self.job.progress
        if processed_seconds is not None and duration > 0:
            fraction = min(1.0, max(0.0, float(processed_seconds) / duration))
            self._update_transcription_estimate_from_throughput(fraction, now)
            next_progress = self._pipeline_progress("transcribing", fraction)

        if next_progress is None:
            next_progress = self.job.progress

        if next_progress == self.job.progress and heartbeat_age < settings.job_heartbeat_interval_seconds:
            return

        self._commit_heartbeat(next_progress, now)

    def _record_stage_heartbeat(self) -> None:
        """Keep long FFmpeg stages visibly alive without imposing a fixed timeout."""
        self._ensure_not_cancelled()
        now = datetime.utcnow()
        last_heartbeat = self.job.heartbeat_at
        if last_heartbeat is not None:
            age = (now - last_heartbeat).total_seconds()
            if age < settings.job_heartbeat_interval_seconds:
                return
        self._commit_heartbeat(self.job.progress, now)

    def _commit_heartbeat(self, progress: int, now: datetime) -> None:
        """Commit liveness with a bounded retry for transient SQLite locks."""
        for attempt in range(3):
            self._ensure_not_cancelled()
            self.job.progress = progress
            self.job.heartbeat_at = now
            self.job.updated_at = now
            try:
                self.db.commit()
                return
            except OperationalError as error:
                self.db.rollback()
                is_locked = "database is locked" in str(error).lower()
                if not is_locked or attempt == 2:
                    raise
                delay_seconds = 0.5 * (attempt + 1)
                logger.warning(
                    f"Job {self.job_id}: SQLite locked while recording heartbeat; "
                    f"retrying in {delay_seconds:.1f}s"
                )
                time.sleep(delay_seconds)

    def _record_stage_duration(self, stage: str, ended_at: datetime) -> None:
        """Accumulate per-stage processing time for API diagnostics."""
        started_at = self.job.stage_started_at
        if not started_at:
            return

        try:
            metrics = json.loads(self.job.stage_metrics_json or "{}")
        except json.JSONDecodeError:
            metrics = {}

        elapsed = max(0.0, (ended_at - started_at).total_seconds())
        metrics[stage] = round(float(metrics.get(stage, 0)) + elapsed, 2)
        self.job.stage_metrics_json = json.dumps(metrics)
        self._stage_occurrences[stage] = self._stage_occurrences.get(stage, 0) + 1
        planned_occurrences = self._planned_stage_occurrences.get(stage, 1)
        if planned_occurrences > 1:
            observed_per_occurrence = float(metrics[stage]) / self._stage_occurrences[stage]
            estimates = self.job.stage_estimates
            estimates[stage] = round(observed_per_occurrence * planned_occurrences, 1)
            self.job.stage_estimates_json = json.dumps(estimates)

    def _update_transcription_estimate_from_throughput(
        self,
        processed_fraction: float,
        now: datetime,
    ) -> None:
        """Replace a generic ETA with the job's observed real-time factor."""
        if processed_fraction < 0.05 or not self.job.stage_started_at:
            return
        elapsed = max(0.1, (now - self.job.stage_started_at).total_seconds())
        projected_total = elapsed / processed_fraction
        estimates = self.job.stage_estimates
        # A small headroom avoids showing an ETA that counts down to zero while
        # the decoder finishes its trailing segment.
        estimates["transcribing"] = round(max(1.0, projected_total * 1.08), 1)
        self.job.stage_estimates_json = json.dumps(estimates)

    def _pipeline_progress(self, status: str, current_fraction: float = 0.0) -> int | None:
        """Derive progress from active plan/measurements instead of fixed bands."""
        estimates = self.job.stage_estimates
        if status not in estimates:
            return None
        total = sum(value for value in estimates.values() if value > 0)
        if total <= 0:
            return None
        metrics = self.job.stage_metrics
        completed = sum(
            min(float(metrics.get(stage, 0.0)), float(estimate))
            for stage, estimate in estimates.items()
            if stage != status
        )
        completed += min(float(metrics.get(status, 0.0)), float(estimates[status]))
        current = max(0.0, min(1.0, current_fraction)) * float(estimates[status])
        return min(99, max(0, int(((completed + current) / total) * 100)))

    def _get_processing_options(self) -> JobProcessingOptions:
        defaults = default_processing_options().model_dump()
        try:
            stored = json.loads(self.job.processing_options or "{}")
            if not isinstance(stored, dict):
                stored = {}
        except json.JSONDecodeError:
            logger.warning(f"Job {self.job_id}: processing_options invalid, using server defaults")
            stored = {}

        allowed = {key: value for key, value in stored.items() if key in defaults}
        return JobProcessingOptions.model_validate({**defaults, **allowed})

    def _create_clip_record(
        self,
        candidate: Candidate,
        position: int,
        segments: list[TimedSegment],
        options: JobProcessingOptions,
    ) -> Clip:
        """Persist one candidate with its initial canonical edit document."""
        # Cues are always prepared from the transcript so captions can be
        # switched on later in the editor; the job option sets the default.
        cues = build_caption_cues(segments, candidate.start_ms, candidate.end_ms)
        edit = default_edit(
            start_ms=candidate.start_ms,
            end_ms=candidate.end_ms,
            output_preset=options.output_preset,
            visual_style=options.visual_style,
            captions_enabled=options.burn_captions,
            cues=cues,
            watermark_enabled=watermark_default(options),
        )
        start = ms_to_seconds(candidate.start_ms)
        end = ms_to_seconds(candidate.end_ms)
        clip = Clip(
            job_id=self.job_id,
            start_time=start,
            end_time=end,
            suggested_start_time=start,
            suggested_end_time=end,
            highlight_score=round(candidate.score, 4),
            analysis_json=json.dumps(candidate.analysis()),
            algorithm_version=candidate.algorithm_version,
            review_status="suggested",
            position=position,
            edit_json=edit.model_dump_json(),
            edit_revision=1,
            status="processing",
        )
        self.db.add(clip)
        self.db.commit()
        return clip

    def _add_warning(self, message: str) -> None:
        """Keep every warning for the job instead of letting the last one win."""
        current = (self.job.warning_message or "").strip()
        self.job.warning_message = f"{current} {message}".strip() if message not in current else current

    @staticmethod
    def _language_warning(options: JobProcessingOptions, result) -> str | None:
        """Flag auto-detection that is unsure or picked an unexpected language."""
        if options.transcript_language != "auto":
            return None
        language = getattr(result, "language", None)
        probability = getattr(result, "language_probability", None)
        if not language:
            return None
        if probability is not None and probability < settings.whisper_language_min_probability:
            return (
                f"Bahasa audio terdeteksi '{language}' dengan keyakinan rendah ({probability:.0%}). "
                "Jika caption/judul salah bahasa, proses ulang dengan bahasa audio yang dipilih manual."
            )
        if language not in {"id", "en", "ms"}:
            return (
                f"Bahasa audio terdeteksi '{language}'. Jika video berbahasa Indonesia atau Inggris, "
                "proses ulang dengan bahasa audio yang dipilih manual."
            )
        return None

    def _needs_transcript(self, options: JobProcessingOptions) -> bool:
        return bool(options.generate_metadata or options.burn_captions)

    def _plan_candidates(
        self,
        options: JobProcessingOptions,
        segments: list[TimedSegment],
    ) -> list[Candidate]:
        """Transcript-boundary candidates; evenly spaced windows without a transcript."""
        duration_ms = seconds_to_ms(self.job.source_duration_seconds or options.max_clip_seconds)
        if duration_ms <= 0:
            return []
        min_ms = seconds_to_ms(options.min_clip_seconds)
        max_ms = seconds_to_ms(options.max_clip_seconds)
        if options.campaign_brief is not None:
            min_ms = max(min_ms, seconds_to_ms(options.campaign_brief.min_clip_seconds))
            max_ms = min(max_ms, seconds_to_ms(options.campaign_brief.max_clip_seconds))
            if min_ms > max_ms:
                min_ms = max_ms
        count = min(self._resolved_clip_count(options), 12)
        if duration_ms < 5_000:
            return []
        return generate_candidates(
            segments,
            duration_ms=duration_ms,
            min_ms=min(min_ms, duration_ms),
            max_ms=min(max_ms, duration_ms),
            count=count,
        )

    def _resolved_clip_count(self, options: JobProcessingOptions) -> int:
        return resolve_clip_count(self.job.source_duration_seconds, options.clip_count)

    def _clip_metadata_context(
        self,
        segments: list[TimedSegment],
        clip_window: ClipWindow,
        processing_options: JobProcessingOptions,
    ) -> str:
        start_ms, end_ms = seconds_to_ms(clip_window.start), seconds_to_ms(clip_window.end)
        clip_text = " ".join(
            s.text for s in segments
            if s.start_ms < end_ms and s.end_ms > start_ms
        ).strip()
        if clip_text:
            return clip_text

        source_name = self.job.source_name or Path(self.job.source_path).name
        if processing_options.metadata_language == "en":
            return (
                f"Source video: {source_name}. "
                f"Selected clip from {clip_window.start:.0f}s to {clip_window.end:.0f}s."
            )
        return (
            f"Video sumber: {source_name}. "
            f"Klip dibuat dari detik {clip_window.start:.0f} sampai {clip_window.end:.0f}."
        )

    async def process(self):
        """
        Run the pipeline: probe -> (audio -> transcript -> normalize) -> candidates
        -> per-candidate initial edit, validated render, and metadata.

        A failed clip does not fail the job; a failed stage before clipping
        marks the job failed with a stable error code.
        """
        audio_path = None
        try:
            self._ensure_not_cancelled()
            processing_options = self._get_processing_options()
            source_path, media = self._prepare_source(processing_options)
            needs_transcript = self._needs_transcript(processing_options) and media.has_audio
            segments: list[TimedSegment] = []

            if needs_transcript:
                # Stage 1: Extract Audio
                self._update_status("extracting", progress=10)
                audio_path = extract_audio(source_path, settings.temp_dir)
                self._ensure_not_cancelled()

                # Stage 2: Transcribe
                self._update_status("transcribing", progress=30)
                try:
                    raw_segments = transcribe(
                        audio_path,
                        on_progress=self._record_transcription_heartbeat,
                        timeout_seconds=self._transcription_timeout_seconds(),
                        heartbeat_interval_seconds=settings.job_heartbeat_interval_seconds,
                        include_word_timestamps=False,
                        language=(
                            None
                            if processing_options.transcript_language == "auto"
                            else processing_options.transcript_language
                        ),
                    )
                except JobCancelled:
                    raise
                except Exception as error:
                    code = (
                        ErrorCode.TRANSCRIPTION_TIMEOUT
                        if type(error).__name__ == "TranscriptionTimeoutError"
                        else ErrorCode.TRANSCRIPTION_FAILED
                    )
                    raise PipelineError(code, str(error)) from error
                self._ensure_not_cancelled()
                segments, report = normalize_segments(
                    raw_segments, seconds_to_ms(self.job.source_duration_seconds) or None
                )
                self.job.transcript_json = json.dumps(segments_to_json(segments))
                summary = self.job.automatic_summary
                summary["transcript"] = {
                    "segments": report.kept_count,
                    "dropped_empty": report.dropped_empty,
                    "dropped_invalid": report.dropped_invalid,
                    "clamped": report.clamped,
                    "reordered": report.reordered,
                    "repetitions_collapsed": report.repetitions_collapsed,
                    "model": settings.whisper_model_size,
                    "requested_language": processing_options.transcript_language,
                    "language": getattr(raw_segments, "language", None),
                    "language_probability": getattr(raw_segments, "language_probability", None),
                }
                language_warning = self._language_warning(processing_options, raw_segments)
                if language_warning:
                    self._add_warning(language_warning)
                self.job.automatic_summary_json = json.dumps(summary)
                self.db.commit()
            else:
                self.job.transcript_json = "[]"
                self.db.commit()

            candidates = self._plan_candidates(processing_options, segments)
            self._ensure_not_cancelled()

            n_clips = len(candidates)
            if n_clips == 0:
                self._add_warning("Video tidak cukup panjang untuk menghasilkan klip.")
                summary = self.job.automatic_summary
                summary["candidate_warning"] = ErrorCode.CANDIDATE_EMPTY.value
                self.job.automatic_summary_json = json.dumps(summary)
                self.db.commit()
                self._update_status("done", progress=100)
                logger.warning(f"Job {self.job_id}: finished dengan 0 clips")
                return

            failed_clips = 0
            source_reference_hashtags = (
                load_youtube_reference_hashtags(source_path)
                if self.job.source_type == "youtube_url"
                else []
            )
            needs_social_render = (
                processing_options.output_preset != "original"
                or processing_options.visual_style != "clean"
            )
            render_stage = "cropping" if needs_social_render else "cutting"
            self._planned_stage_occurrences = {
                render_stage: n_clips,
                **({"generating_metadata": n_clips} if processing_options.generate_metadata else {}),
            }
            for clip_idx, candidate in enumerate(candidates):
                clip = None
                try:
                    self._ensure_not_cancelled()
                    clip = self._create_clip_record(candidate, clip_idx + 1, segments, processing_options)

                    self._update_status(render_stage)
                    outcome = render_edit_to_file(
                        source_path=source_path,
                        source=media,
                        edit=ClipEdit.model_validate_json(clip.edit_json),
                        clip_id=clip.id,
                        revision=int(clip.edit_revision),
                        acceleration=processing_options.render_acceleration,
                        on_heartbeat=self._record_stage_heartbeat,
                        heartbeat_seconds=settings.job_heartbeat_interval_seconds,
                    )
                    self._ensure_not_cancelled()

                    metadata = {}
                    if processing_options.generate_metadata:
                        self._update_status("generating_metadata")
                        metadata_context = self._clip_metadata_context(
                            segments,
                            ClipWindow(
                                start=ms_to_seconds(candidate.start_ms),
                                end=ms_to_seconds(candidate.end_ms),
                            ),
                            processing_options,
                        )
                        metadata = generate_metadata(
                            metadata_context,
                            processing_options.metadata_language,
                            source_reference_hashtags,
                            processing_options.campaign_brief,
                        )
                        self._ensure_not_cancelled()

                    apply_render_success(clip, outcome, int(clip.edit_revision))
                    clip.title = metadata.get("title")
                    clip.caption = metadata.get("caption")
                    clip.hashtags = json.dumps(metadata.get("hashtags", []))
                    self.db.commit()
                    logger.info(f"Clip {clip.id} selesai: {clip.title}")

                except JobCancelled:
                    logger.info(f"Job {self.job_id}: cancelled saat memproses clip")
                    raise
                except Exception as e:
                    logger.error(f"Error processing clip {clip_idx} pada job {self.job_id}: {e}")
                    # Mark the clip failed, but continue with the next candidate.
                    failed_clips += 1
                    self.db.rollback()
                    if clip is not None:
                        code, message = describe_failure(e)
                        clip.status = "failed"
                        clip.render_error_code = (
                            ErrorCode.EXPORT_FAILED.value if code == ErrorCode.UNKNOWN else code.value
                        )
                        clip.render_error_message = message
                    self.db.commit()
                    continue

            # Mark job done
            if failed_clips:
                self._add_warning(f"{failed_clips} clip gagal dibuat. Periksa status clip untuk detailnya.")
                self.db.commit()
            self._update_status("done", progress=100)
            logger.info(f"Job {self.job_id} completed successfully")

        except JobCancelled:
            self.db.rollback()
            logger.info(f"Job {self.job_id}: processing stopped karena cancelled")
        except Exception as e:
            # A failed commit leaves SQLAlchemy's transaction unusable until a
            # rollback.  Recover it before recording the terminal job status.
            self.db.rollback()
            logger.error(f"Fatal error di job {self.job_id}: {e}", exc_info=True)
            code, message = describe_failure(e)
            try:
                self._update_status("failed", progress=0, error_msg=message, error_code=code.value)
            except JobCancelled:
                self.db.rollback()
                logger.info(f"Job {self.job_id}: fatal error ignored karena job sudah cancelled")
            except Exception as status_error:
                self.db.rollback()
                logger.error(
                    f"Job {self.job_id}: unable to persist failed status: {status_error}",
                    exc_info=True,
                )
        finally:
            if audio_path is not None:
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except OSError as error:
                    logger.warning(f"Job {self.job_id}: failed deleting temporary audio: {error}")

    def _prepare_source(self, processing_options: JobProcessingOptions) -> tuple[Path, MediaFacts]:
        """Download a queued YouTube source when needed and persist the actual media facts."""
        stored_source = self.job.source_path
        source_path = Path(stored_source)
        if self.job.source_type == "youtube_url" and stored_source.startswith(("http://", "https://")):
            # Repeat the submission gate immediately before yt-dlp in case a
            # previous queued job received a bot block while this one waited.
            # This performs no outbound request when access is on cooldown.
            require_youtube_access()
            self._update_status("downloading", progress=5)
            source_path = download_youtube_video(
                self.job.source_path,
                settings.upload_dir,
                self.job_id,
                settings.youtube_download_timeout_seconds,
                settings.youtube_download_concurrent_fragments,
                settings.youtube_download_max_height,
                settings.youtube_cookies_path,
                settings.youtube_user_agent,
            )
            self._ensure_not_cancelled()
            self.job.source_name = self._youtube_source_name() or self.job.source_name

        if not source_path.exists():
            raise PipelineError(ErrorCode.SOURCE_MISSING)

        media = probe_media(source_path)
        if media is None:
            raise PipelineError(ErrorCode.SOURCE_CORRUPT, "ffprobe tidak menemukan stream video")
        if processing_options.generate_metadata and not media.has_audio:
            raise PipelineError(ErrorCode.AUDIO_MISSING)
        video_info = media

        self.job.source_path = str(source_path)
        self.job.source_duration_seconds = video_info.duration_seconds
        self.job.source_size_bytes = source_path.stat().st_size
        stage_estimates, factors = calibrate_stage_estimates(
            self.db,
            self.job.source_type,
            build_stage_estimates(video_info.duration_seconds, self.job.source_type, processing_options),
        )
        self.job.stage_estimates_json = json.dumps(stage_estimates)
        if self.job.source_type == "youtube_url" and processing_options.processing_mode == "automatic":
            summary = self.job.automatic_summary
            summary["eta_calibration_factors"] = factors
            self.job.automatic_summary_json = json.dumps(summary)
        self.db.commit()
        return source_path, media

    def _youtube_source_name(self) -> str | None:
        info_path = settings.upload_dir / f"{self.job_id}.info.json"
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        title = str(info.get("title") or "").strip()
        uploader = str(info.get("uploader") or info.get("channel") or "").strip()
        if title and uploader:
            return f"{title} - {uploader}"[:250]
        if title:
            return title[:250]
        return None
