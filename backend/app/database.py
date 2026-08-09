"""
Database setup. SQLite via SQLAlchemy — pilihan ini dijelaskan di
ARCHITECTURE.md bagian 2. Interface Session di sini dibuat generic
supaya swap ke Postgres nanti tinggal ganti database_url.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# check_same_thread=False diperlukan karena FastAPI bisa akses DB
# dari thread berbeda (background task worker)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — 1 session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Buat tabel dan upgrade ringan untuk database SQLite yang sudah ada."""
    from app import models  # noqa: F401 — registrasi model ke Base.metadata
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_schema_upgrades()


def _apply_sqlite_schema_upgrades():
    """Keep the personal SQLite database compatible without an Alembic dependency."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("jobs")}
    upgrades = {
        "source_name": "VARCHAR",
        "source_duration_seconds": "FLOAT",
        "source_size_bytes": "INTEGER",
        "processing_options": "TEXT",
        "parent_job_id": "VARCHAR",
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "warning_message": "TEXT",
        "stage_metrics_json": "TEXT",
        "stage_estimates_json": "TEXT",
        "processing_started_at": "DATETIME",
        "stage_started_at": "DATETIME",
        "completed_at": "DATETIME",
    }

    with engine.begin() as connection:
        for column_name, column_definition in upgrades.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_definition}")
                )


ACTIVE_INTERRUPTIBLE_JOB_STATUSES = (
    "downloading",
    "extracting",
    "transcribing",
    "detecting",
    "cutting",
    "cropping",
    "subtitling",
    "generating_metadata",
)


@dataclass(frozen=True)
class StartupRecoveryReport:
    pending_job_ids: tuple[str, ...] = ()
    failed_jobs: int = 0
    failed_clips: int = 0


def recover_jobs_after_startup() -> StartupRecoveryReport:
    """
    Recover open jobs after backend startup.

    Pending jobs are safe to queue again because no pipeline stage has started.
    Jobs already inside a processing stage are not resumed automatically, because
    rerunning them in-place can duplicate clips or mix old/new artifacts.
    """
    from app.models import Clip, Job

    with SessionLocal() as db:
        now = datetime.utcnow()
        pending_job_ids = tuple(
            job_id
            for (job_id,) in (
                db.query(Job.id)
                .filter(Job.status == "pending")
                .order_by(Job.created_at.asc())
                .all()
            )
        )
        if pending_job_ids:
            (
                db.query(Job)
                .filter(Job.id.in_(pending_job_ids))
                .update(
                    {
                        Job.error_message: None,
                        Job.progress: 0,
                        Job.processing_started_at: None,
                        Job.stage_started_at: None,
                        Job.completed_at: None,
                        Job.updated_at: now,
                    },
                    synchronize_session=False,
                )
            )

        message = (
            "Interrupted by backend restart while processing; "
            "create a retry job to process this source again."
        )
        failed_jobs = (
            db.query(Job)
            .filter(Job.status.in_(ACTIVE_INTERRUPTIBLE_JOB_STATUSES))
            .update(
                {
                    Job.status: "failed",
                    Job.error_message: message,
                    Job.updated_at: now,
                    Job.completed_at: now,
                    Job.stage_started_at: None,
                },
                synchronize_session=False,
            )
        )

        failed_clips = 0
        if failed_jobs:
            failed_clips = (
                db.query(Clip)
                .filter(Clip.status == "processing")
                .update({Clip.status: "failed"}, synchronize_session=False)
            )

        db.commit()
        return StartupRecoveryReport(
            pending_job_ids=pending_job_ids,
            failed_jobs=failed_jobs,
            failed_clips=failed_clips,
        )


def mark_interrupted_jobs_failed() -> int:
    """Backward-compatible wrapper for older tests/tools."""
    return recover_jobs_after_startup().failed_jobs
