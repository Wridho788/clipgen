"""
ORM models. Lihat ARCHITECTURE.md bagian 2 untuk rasionalisasi schema.
"""
import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base

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


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    source_type = Column(String, nullable=False)  # "upload" | "youtube_url"
    source_path = Column(String, nullable=False)
    source_name = Column(String, nullable=True)
    source_duration_seconds = Column(Float, nullable=True)
    source_size_bytes = Column(Integer, nullable=True)
    processing_options = Column(Text, nullable=True)
    parent_job_id = Column(String, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending")
    progress = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    warning_message = Column(Text, nullable=True)
    transcript_json = Column(Text, nullable=True)
    stage_metrics_json = Column(Text, nullable=True)
    stage_estimates_json = Column(Text, nullable=True)
    automatic_summary_json = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    stage_started_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="jobs")
    clips = relationship("Clip", back_populates="job", cascade="all, delete-orphan")

    @property
    def stage_metrics(self) -> dict[str, float]:
        return _json_number_map(self.stage_metrics_json)

    @property
    def stage_estimates(self) -> dict[str, float]:
        return _json_number_map(self.stage_estimates_json)

    @property
    def automatic_summary(self) -> dict[str, object]:
        return _json_object_map(self.automatic_summary_json)

    @property
    def estimated_total_seconds(self) -> float:
        return round(sum(self.stage_estimates.values()), 1)

    @property
    def current_stage_eta_seconds(self) -> float:
        if self.status in {"done", "failed", "cancelled"}:
            return 0.0
        if self.status == "pending":
            for stage, estimate in self.stage_estimates.items():
                if estimate > 0:
                    return round(estimate, 1)
            return 0.0
        return round(self._remaining_for_stage(self.status, is_current=True), 1)

    @property
    def current_stage_elapsed_seconds(self) -> float:
        """Expose the live stage elapsed time for honest job monitoring."""
        if self.status in {"pending", "done", "failed", "cancelled"}:
            return 0.0
        return round(_elapsed_seconds(self.stage_started_at), 1)

    @property
    def overall_eta_seconds(self) -> float:
        if self.status in {"done", "failed", "cancelled"}:
            return 0.0
        if self.status == "pending":
            return self.estimated_total_seconds

        stages = _stage_order_for_job(self.source_type, self.stage_estimates, self.status)
        if self.status not in stages:
            return round(
                max(0.0, self.estimated_total_seconds - sum(self.stage_metrics.values())),
                1,
            )

        current_index = stages.index(self.status)
        remaining = 0.0
        for index, stage in enumerate(stages[current_index:]):
            remaining += self._remaining_for_stage(stage, is_current=index == 0)
        return round(remaining, 1)

    @property
    def estimated_completion_at(self):
        if self.status in {"done", "failed", "cancelled"}:
            return None
        return datetime.utcnow() + timedelta(seconds=self.overall_eta_seconds)

    def _remaining_for_stage(self, stage: str, is_current: bool) -> float:
        estimate = self.stage_estimates.get(stage, 0.0)
        recorded = self.stage_metrics.get(stage, 0.0)
        current_elapsed = _elapsed_seconds(self.stage_started_at) if is_current else 0.0
        planned_remaining = estimate - recorded - current_elapsed
        if planned_remaining > 0:
            return planned_remaining
        if is_current and current_elapsed > 0:
            # A stage can legitimately exceed its baseline on slower CPUs or long videos.
            # Keep an adaptive non-zero ETA until the worker moves to the next stage.
            return max(5.0, current_elapsed * 0.5)
        return 0.0


class Clip(Base):
    __tablename__ = "clips"

    id = Column(String, primary_key=True, default=gen_uuid)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)

    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    highlight_score = Column(Float, nullable=False, default=0.0)

    file_path = Column(String, nullable=True)
    title = Column(String, nullable=True)
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)  # JSON-encoded list[str]

    status = Column(String, nullable=False, default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="clips")
    feedback = relationship("ClipFeedback", back_populates="clip", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs = relationship("Job", back_populates="owner")
    feedback = relationship("ClipFeedback", back_populates="user", cascade="all, delete-orphan")


class ClipFeedback(Base):
    __tablename__ = "clip_feedback"
    __table_args__ = (UniqueConstraint("clip_id", "user_id", name="uq_clip_feedback_user"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    clip_id = Column(String, ForeignKey("clips.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # -1 irrelevant, 1 useful
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clip = relationship("Clip", back_populates="feedback")
    user = relationship("User", back_populates="feedback")


def _json_number_map(raw_value: str | None) -> dict[str, float]:
    try:
        parsed = json.loads(raw_value or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    result = {}
    for key, value in parsed.items():
        try:
            result[str(key)] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return result


def _json_object_map(raw_value: str | None) -> dict[str, object]:
    try:
        parsed = json.loads(raw_value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _elapsed_seconds(started_at: datetime | None) -> float:
    if not started_at:
        return 0.0
    return max(0.0, (datetime.utcnow() - started_at).total_seconds())


def _stage_order_for_job(
    source_type: str,
    stage_estimates: dict[str, float],
    current_status: str,
) -> tuple[str, ...]:
    stages = tuple(
        stage for stage in STAGE_ORDER
        if stage in stage_estimates or stage == current_status
    )
    if stages:
        return stages

    legacy_stages = ("extracting", "transcribing", "detecting", "cutting")
    if source_type == "youtube_url":
        return ("downloading",) + legacy_stages + ("subtitling", "generating_metadata")
    return legacy_stages + ("generating_metadata",)
