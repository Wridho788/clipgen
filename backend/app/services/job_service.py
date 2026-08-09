"""
Job Service — orchestrator yang mengelola job lifecycle.
Ini interface antara API routes dan pipeline stages.

Satu instance JobService handle satu job, call stages satu-satu,
update DB status + progress, handle error per stage.
"""
import json
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.models import Job, Clip
from app.schemas import JobProcessingOptions, default_processing_options
from app.core.pipeline.audio_extract import extract_audio, has_audio_stream
from app.core.pipeline.transcribe import transcribe
from app.core.pipeline.highlight_detect import Highlight, detect_highlights
from app.core.pipeline.clip_cut import cut_clip
from app.core.pipeline.subtitle_burn import burn_subtitles
from app.core.pipeline.metadata_gen import generate_metadata
from app.core.pipeline.vertical_crop import crop_clip_vertical
from app.services.media_probe import probe_video
from app.services.processing_estimator import build_stage_estimates
from app.services.youtube_downloader import download_youtube_video


class JobCancelled(Exception):
    """Raised internally when a queued/running job has been cancelled."""


class JobService:
    """Manage satu job dari start sampai selesai."""

    def __init__(self, job_id: str, db: Session):
        self.job_id = job_id
        self.db = db
        self.job = db.query(Job).filter(Job.id == job_id).first()
        if not self.job:
            raise ValueError(f"Job {job_id} not found")

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
            "detecting",
            "cutting",
            "cropping",
            "downloading",
            "subtitling",
            "generating_metadata",
        }

        if previous_status in active_stages and previous_status != status:
            self._record_stage_duration(previous_status, now)

        self.job.status = status
        if progress is not None:
            self.job.progress = progress
        if error_msg:
            self.job.error_message = error_msg
        if status in active_stages:
            if self.job.processing_started_at is None:
                self.job.processing_started_at = now
            self.job.stage_started_at = now
        elif status in {"done", "failed"}:
            self.job.completed_at = now
            self.job.stage_started_at = None
            if status == "done":
                self.job.error_message = None
        self.job.updated_at = now
        self.db.commit()
        logger.info(f"Job {self.job_id}: status={status}, progress={progress}, error={error_msg}")

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
        for suffix in ("_raw.mp4", "_cropped.mp4", "_subs.srt"):
            candidate = settings.clips_dir / f"{clip_id}{suffix}"
            if candidate == final_path:
                continue
            try:
                candidate.unlink(missing_ok=True)
            except OSError as error:
                logger.warning(f"Job {self.job_id}: failed deleting {candidate.name}: {error}")

    def _create_clip_record(self, start: float, end: float, score: float) -> Clip:
        """Buat record clip di DB, status processing."""
        clip = Clip(
            job_id=self.job_id,
            start_time=start,
            end_time=end,
            highlight_score=score,
            status="processing",
        )
        self.db.add(clip)
        self.db.commit()
        return clip

    def _needs_transcript(self, options: JobProcessingOptions) -> bool:
        return bool(options.generate_highlights or options.generate_subtitles)

    def _default_highlights(self, options: JobProcessingOptions) -> list[Highlight]:
        """Build a deterministic clip window when highlight generation is disabled."""
        duration = float(self.job.source_duration_seconds or options.max_clip_seconds)
        if duration <= 0:
            return []
        end = min(duration, float(options.max_clip_seconds))
        return [Highlight(start=0.0, end=max(1.0, end), score=0.5)]

    def _automatic_youtube_intro_skip_seconds(self, options: JobProcessingOptions) -> float:
        """Skip a likely intro/montage without exhausting short source videos."""
        if self.job.source_type != "youtube_url" or options.processing_mode != "automatic":
            return 0.0

        duration = max(0.0, float(self.job.source_duration_seconds or 0))
        wanted_content = float(options.min_clip_seconds) * max(3, int(options.clip_count))
        max_safe_skip = max(0.0, duration - wanted_content)
        return min(settings.automatic_youtube_intro_skip_seconds, max_safe_skip)

    def _clip_metadata_context(
        self,
        segments,
        highlight: Highlight,
        processing_options: JobProcessingOptions,
    ) -> str:
        clip_text = " ".join(
            s.text for s in segments
            if s.start < highlight.end and s.end > highlight.start
        ).strip()
        if clip_text:
            return clip_text

        source_name = self.job.source_name or Path(self.job.source_path).name
        if processing_options.metadata_language == "en":
            return (
                f"Source video: {source_name}. "
                f"Selected clip from {highlight.start:.0f}s to {highlight.end:.0f}s."
            )
        return (
            f"Video sumber: {source_name}. "
            f"Klip dipilih dari detik {highlight.start:.0f} sampai {highlight.end:.0f}."
        )

    async def process(self):
        """
        Jalankan pipeline sesuai opsi job. Upload lokal default tetap memakai
        transcribe/detect/metadata seperti perilaku lama, sementara YouTube
        Automatic YouTube analysis skips the opening montage/intro when safe,
        detects several distinct highlights, and keeps landscape/subtitles off.
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
                segments = transcribe(audio_path)
                self._ensure_not_cancelled()
                self.job.transcript_json = json.dumps(
                    [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
                )
                self.db.commit()
            else:
                self.job.transcript_json = "[]"
                self.db.commit()

            if processing_options.generate_highlights:
                # Stage 3: Detect Highlights
                self._update_status("detecting", progress=50)
                duration = segments[-1].end if segments else self.job.source_duration_seconds or 0
                highlights = detect_highlights(
                    segments,
                    audio_path,
                    duration,
                    min_clip_seconds=processing_options.min_clip_seconds,
                    max_clip_seconds=processing_options.max_clip_seconds,
                    top_n=processing_options.clip_count,
                    exclude_before_seconds=self._automatic_youtube_intro_skip_seconds(processing_options),
                    min_separation_seconds=(
                        settings.automatic_youtube_min_segment_gap_seconds
                        if processing_options.processing_mode == "automatic"
                        else 0
                    ),
                )
                self._ensure_not_cancelled()

                if not highlights:
                    logger.warning(f"Job {self.job_id}: tidak ada highlight terdeteksi")
                    highlights = []  # proceed dengan empty, jangan fail total
            else:
                highlights = self._default_highlights(processing_options)
                logger.info(f"Job {self.job_id}: highlight detection skipped, using default clip window")

            # Stage 4 onward: Per-clip processing
            n_clips = len(highlights)
            if n_clips == 0:
                self.job.warning_message = "Tidak ada highlight yang cukup kuat terdeteksi dari video ini."
                self.db.commit()
                self._update_status("done", progress=100)
                logger.warning(f"Job {self.job_id}: finished dengan 0 clips")
                return

            failed_clips = 0
            for clip_idx, highlight in enumerate(highlights):
                clip = None
                try:
                    self._ensure_not_cancelled()
                    # Progress dibagi sesuai jumlah treatment yang benar-benar aktif.
                    base_progress = 50 if processing_options.generate_highlights else (35 if needs_transcript else 10)
                    stage_count = (
                        1
                        + int(processing_options.crop_vertical)
                        + int(processing_options.generate_subtitles)
                        + int(processing_options.generate_metadata)
                    )
                    total_clip_steps = n_clips * stage_count

                    def clip_progress(stage_index: int) -> int:
                        completed_steps = clip_idx * stage_count + stage_index
                        return min(99, int(base_progress + (completed_steps / total_clip_steps) * (99 - base_progress)))

                    # Create clip record
                    clip = self._create_clip_record(highlight.start, highlight.end, highlight.score)

                    # Stage 4: Cut raw clip
                    stage_index = 0
                    self._update_status("cutting", progress=clip_progress(stage_index))
                    raw_clip_path = cut_clip(
                        source_path, highlight.start, highlight.end, settings.clips_dir, clip.id
                    )
                    self._ensure_not_cancelled()
                    final_clip_path = raw_clip_path
                    stage_index += 1

                    if processing_options.crop_vertical:
                        self._update_status("cropping", progress=clip_progress(stage_index))
                        final_clip_path = crop_clip_vertical(final_clip_path, settings.clips_dir, clip.id)
                        self._ensure_not_cancelled()
                        stage_index += 1

                    if processing_options.generate_subtitles:
                        self._update_status("subtitling", progress=clip_progress(stage_index))
                        final_clip_path = burn_subtitles(
                            final_clip_path,
                            segments,
                            clip.id,
                            settings.clips_dir,
                            clip_start_time=highlight.start,
                        )
                        self._ensure_not_cancelled()
                        stage_index += 1

                    metadata = {}
                    if processing_options.generate_metadata:
                        self._update_status("generating_metadata", progress=clip_progress(stage_index))
                        metadata_context = self._clip_metadata_context(
                            segments,
                            highlight,
                            processing_options,
                        )
                        metadata = generate_metadata(metadata_context, processing_options.metadata_language)
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
            logger.error(f"Fatal error di job {self.job_id}: {e}", exc_info=True)
            try:
                self._update_status("failed", progress=0, error_msg=str(e)[:500])
            except JobCancelled:
                self.db.rollback()
                logger.info(f"Job {self.job_id}: fatal error ignored karena job sudah cancelled")
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
            self._update_status("downloading", progress=5)
            source_path = download_youtube_video(
                self.job.source_path,
                settings.upload_dir,
                self.job_id,
                settings.youtube_download_timeout_seconds,
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
        self.job.stage_estimates_json = json.dumps(
            build_stage_estimates(video_info.duration_seconds, self.job.source_type, processing_options)
        )
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
