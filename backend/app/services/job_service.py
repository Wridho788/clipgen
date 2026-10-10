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
from app.core.pipeline.audio_extract import extract_audio, has_audio_stream
from app.core.pipeline.transcribe import transcribe
from app.core.pipeline.clip_cut import cut_clip
from app.core.pipeline.metadata_gen import generate_metadata
from app.core.pipeline.social_render import render_social_clip
from app.services.media_probe import probe_video
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

    def _update_status(self, status: str, progress: int = None, error_msg: str = None):
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

    def _cleanup_clip_intermediates(self, clip_id: str, final_path: Path) -> None:
        """Keep only the final user-facing video; failed artifacts are cleaned by maintenance."""
        for suffix in ("_raw.mp4", "_cropped.mp4", "_rendered.mp4", "_subs.srt", "_subs.ass"):
            candidate = settings.clips_dir / f"{clip_id}{suffix}"
            if candidate == final_path:
                continue
            try:
                candidate.unlink(missing_ok=True)
            except OSError as error:
                logger.warning(f"Job {self.job_id}: failed deleting {candidate.name}: {error}")

    def _create_clip_record(
        self,
        start: float,
        end: float,
    ) -> Clip:
        """Buat record clip di DB, status processing."""
        clip = Clip(
            job_id=self.job_id,
            start_time=start,
            end_time=end,
            highlight_score=0.0,
            status="processing",
        )
        self.db.add(clip)
        self.db.commit()
        return clip

    def _needs_transcript(self, options: JobProcessingOptions) -> bool:
        return bool(options.generate_metadata)

    def _plan_clip_windows(self, options: JobProcessingOptions) -> list[ClipWindow]:
        """Select evenly spaced windows without scoring or ranking moments."""
        duration = float(self.job.source_duration_seconds or options.max_clip_seconds)
        if duration <= 0:
            return []
        count = min(self._resolved_clip_count(options), 12)
        clip_duration = min(float(options.max_clip_seconds), duration / count)
        if count <= 1:
            starts = [0.0]
        else:
            last_start = max(0.0, duration - clip_duration)
            starts = [last_start * index / (count - 1) for index in range(count)]
        return [
            ClipWindow(start=start, end=min(duration, start + clip_duration))
            for start in starts
        ]

    def _resolved_clip_count(self, options: JobProcessingOptions) -> int:
        return resolve_clip_count(self.job.source_duration_seconds, options.clip_count)

    def _clip_metadata_context(
        self,
        segments,
        clip_window: ClipWindow,
        processing_options: JobProcessingOptions,
    ) -> str:
        clip_text = " ".join(
            s.text for s in segments
            if s.start < clip_window.end and s.end > clip_window.start
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
        Jalankan pipeline sesuai opsi job. Semua sumber dibagi menjadi jendela
        klip dengan jarak merata; format sosial tetap mengikuti opsi job.
        Jika ada error di stage tertentu, set job.status=failed dan return early.
        """
        audio_path = None
        try:
            self._ensure_not_cancelled()
            processing_options = self._get_processing_options()
            source_path = self._prepare_source(processing_options)
            needs_transcript = self._needs_transcript(processing_options)
            segments = []

            if needs_transcript:
                # Stage 1: Extract Audio
                self._update_status("extracting", progress=10)
                audio_path = extract_audio(source_path, settings.temp_dir)
                self._ensure_not_cancelled()

                # Stage 2: Transcribe
                self._update_status("transcribing", progress=30)
                segments = transcribe(
                    audio_path,
                    on_progress=self._record_transcription_heartbeat,
                    timeout_seconds=self._transcription_timeout_seconds(),
                    heartbeat_interval_seconds=settings.job_heartbeat_interval_seconds,
                    include_word_timestamps=False,
                )
                self._ensure_not_cancelled()
                self.job.transcript_json = json.dumps(
                    [
                        {
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text,
                            "words": [
                                {"start": word.start, "end": word.end, "text": word.text}
                                for word in segment.words
                            ],
                        }
                        for segment in segments
                    ]
                )
                self.db.commit()
            else:
                self.job.transcript_json = "[]"
                self.db.commit()

            clip_windows = self._plan_clip_windows(processing_options)
            self._ensure_not_cancelled()

            # Stage 4 onward: Per-clip processing
            n_clips = len(clip_windows)
            if n_clips == 0:
                self.job.warning_message = "Video tidak cukup panjang untuk menghasilkan klip."
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
            # Automatic jobs are designed as clean source-first exports. The
            # explicit empty string prevents render helpers from falling back
            # to the global watermark setting; manual jobs retain that setting.
            watermark_text = "" if processing_options.processing_mode == "automatic" else None
            self._planned_stage_occurrences = {
                ("cropping" if needs_social_render else "cutting"): n_clips,
                **({"generating_metadata": n_clips} if processing_options.generate_metadata else {}),
            }
            for clip_idx, clip_window in enumerate(clip_windows):
                clip = None
                try:
                    self._ensure_not_cancelled()
                    # Create clip record
                    clip = self._create_clip_record(
                        clip_window.start,
                        clip_window.end,
                    )

                    if needs_social_render:
                        # One FFmpeg pass: seek/cut + social reframe + final encode.
                        self._update_status("cropping")
                        final_clip_path = render_social_clip(
                            source_path,
                            settings.clips_dir,
                            clip.id,
                            output_preset=processing_options.output_preset,
                            visual_style=processing_options.visual_style,
                            acceleration=processing_options.render_acceleration,
                            start_time=clip_window.start,
                            end_time=clip_window.end,
                            on_heartbeat=self._record_stage_heartbeat,
                            heartbeat_seconds=settings.job_heartbeat_interval_seconds,
                            watermark_text=watermark_text,
                        )
                        self._ensure_not_cancelled()
                    else:
                        self._update_status("cutting")
                        final_clip_path = cut_clip(
                            source_path,
                            clip_window.start,
                            clip_window.end,
                            settings.clips_dir,
                            clip.id,
                            processing_options.render_acceleration,
                            on_heartbeat=self._record_stage_heartbeat,
                            heartbeat_seconds=settings.job_heartbeat_interval_seconds,
                            watermark_text=watermark_text,
                        )
                        self._ensure_not_cancelled()

                    metadata = {}
                    if processing_options.generate_metadata:
                        self._update_status("generating_metadata")
                        metadata_context = self._clip_metadata_context(
                            segments,
                            clip_window,
                            processing_options,
                        )
                        metadata = generate_metadata(
                            metadata_context,
                            processing_options.metadata_language,
                            source_reference_hashtags,
                            processing_options.campaign_brief,
                        )
                        self._ensure_not_cancelled()

                    # Update clip record dengan hasil akhir
                    clip.file_path = str(final_clip_path)
                    clip.title = metadata.get("title")
                    clip.caption = metadata.get("caption")
                    clip.hashtags = json.dumps(metadata.get("hashtags", []))
                    clip.status = "ready"
                    self.db.commit()
                    self._cleanup_clip_intermediates(clip.id, final_clip_path)

                    logger.info(f"Clip {clip.id} selesai: {clip.title}")

                except JobCancelled:
                    logger.info(f"Job {self.job_id}: cancelled saat memproses clip")
                    raise
                except Exception as e:
                    logger.error(f"Error processing clip {clip_idx} pada job {self.job_id}: {e}")
                    # Mark clip sebagai failed, tapi continue ke clip berikutnya (jangan fail total job)
                    failed_clips += 1
                    if clip is not None:
                        clip.status = "failed"
                    self.db.commit()
                    continue

            # Mark job done
            if failed_clips:
                self.job.warning_message = f"{failed_clips} clip gagal dibuat. Periksa status clip untuk detailnya."
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
            try:
                self._update_status("failed", progress=0, error_msg=str(e)[:500])
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

    def _prepare_source(self, processing_options: JobProcessingOptions) -> Path:
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
            raise FileNotFoundError("File sumber tidak ditemukan. Upload ulang video untuk memprosesnya.")

        video_info = probe_video(source_path)
        if not video_info:
            raise ValueError("File video tidak valid atau corrupt setelah diterima.")
        if self._needs_transcript(processing_options) and not has_audio_stream(source_path):
            raise ValueError("Video tidak punya audio track. Gunakan video dengan suara/speech.")

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
        return source_path

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
