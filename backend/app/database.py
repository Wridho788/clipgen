"""
Database setup. SQLite via SQLAlchemy (lihat docs/08-repository-audit.md).
Interface Session di sini dibuat generic supaya swap ke Postgres nanti tinggal
ganti database_url.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# check_same_thread=False diperlukan karena FastAPI bisa akses DB
# dari thread berbeda (background task worker).  The timeout prevents a short
# dashboard read/write overlap from aborting a long-running worker heartbeat.
_sqlite_connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(settings.database_url, connect_args=_sqlite_connect_args)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record):
        """Configure every SQLite connection for concurrent local API usage."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout = 30000")
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()

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
    _configure_sqlite_journal()
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_schema_upgrades()
    _ensure_local_owner()


def _configure_sqlite_journal() -> None:
    """Enable WAL so dashboard reads do not block a processing heartbeat."""
    if engine.dialect.name != "sqlite":
        return

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.exec_driver_sql("PRAGMA synchronous=NORMAL")
        connection.commit()


SCHEMA_VERSION = 3


def _apply_sqlite_schema_upgrades():
    """Apply numbered, recorded schema migrations (docs/02 §6).

    Kept dependency-free for the personal SQLite deployment. Each migration is
    idempotent (it inspects existing columns first) so databases created by
    ``create_all`` and legacy databases converge on the same schema. Applied
    versions are recorded in ``schema_migrations``; unknown columns are never
    dropped.
    """
    if engine.dialect.name != "sqlite":
        return
    run_migrations()


def run_migrations(target_engine=None) -> list[int]:
    """Apply pending migrations and return the versions applied in this call."""
    target_engine = target_engine or engine
    with target_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version INTEGER PRIMARY KEY, name VARCHAR NOT NULL, applied_at DATETIME NOT NULL)"
            )
        )
        applied = {
            int(row[0]) for row in connection.execute(text("SELECT version FROM schema_migrations"))
        }

    newly_applied: list[int] = []
    for version, name, migration in MIGRATIONS:
        if version in applied:
            continue
        with target_engine.begin() as connection:
            migration(connection)
            connection.execute(
                text("INSERT INTO schema_migrations (version, name, applied_at) VALUES (:v, :n, :t)"),
                {"v": version, "n": name, "t": datetime.utcnow()},
            )
        newly_applied.append(version)
    return newly_applied


def current_schema_version(target_engine=None) -> int:
    target_engine = target_engine or engine
    with target_engine.connect() as connection:
        if "schema_migrations" not in inspect(connection).get_table_names():
            return 0
        value = connection.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar()
    return int(value or 0)


def _add_missing_columns(connection, table: str, columns: dict[str, str]) -> None:
    inspector = inspect(connection)
    if table not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(table)}
    for column_name, column_definition in columns.items():
        if column_name not in existing:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_definition}"))


def _migration_001_v1_columns(connection) -> None:
    """Columns added during v1 development (previously ad-hoc upgrades)."""
    _add_missing_columns(
        connection,
        "jobs",
        {
            "source_name": "VARCHAR",
            "owner_id": "VARCHAR",
            "source_duration_seconds": "FLOAT",
            "source_size_bytes": "INTEGER",
            "processing_options": "TEXT",
            "parent_job_id": "VARCHAR",
            "retry_count": "INTEGER NOT NULL DEFAULT 0",
            "warning_message": "TEXT",
            "stage_metrics_json": "TEXT",
            "stage_estimates_json": "TEXT",
            "automatic_summary_json": "TEXT",
            "processing_started_at": "DATETIME",
            "stage_started_at": "DATETIME",
            "heartbeat_at": "DATETIME",
            "completed_at": "DATETIME",
        },
    )
    _add_missing_columns(connection, "clips", {"analysis_json": "TEXT"})


def _migration_002_candidate_review_and_edits(connection) -> None:
    """Candidate review state, canonical edit document, and render diagnostics."""
    _add_missing_columns(connection, "jobs", {"error_code": "VARCHAR"})
    _add_missing_columns(
        connection,
        "clips",
        {
            "review_status": "VARCHAR NOT NULL DEFAULT 'suggested'",
            "review_reason": "VARCHAR",
            "algorithm_version": "VARCHAR",
            "suggested_start_time": "FLOAT",
            "suggested_end_time": "FLOAT",
            "edit_json": "TEXT",
            "edit_revision": "INTEGER NOT NULL DEFAULT 0",
            "rendered_revision": "INTEGER",
            "render_error_code": "VARCHAR",
            "render_error_message": "TEXT",
            "render_report_json": "TEXT",
            "position": "INTEGER",
            "exported_at": "DATETIME",
            "updated_at": "DATETIME",
        },
    )
    if "clips" not in inspect(connection).get_table_names():
        return
    # Existing clips keep their current range as the "AI suggestion" so the
    # editor's reset button and boundary-correction metrics stay meaningful.
    connection.execute(
        text(
            "UPDATE clips SET suggested_start_time = start_time "
            "WHERE suggested_start_time IS NULL"
        )
    )
    connection.execute(
        text("UPDATE clips SET suggested_end_time = end_time WHERE suggested_end_time IS NULL")
    )
    connection.execute(
        text(
            "UPDATE clips SET rendered_revision = 0 "
            "WHERE rendered_revision IS NULL AND file_path IS NOT NULL"
        )
    )
    connection.execute(
        text(
            "UPDATE clips SET algorithm_version = 'even-spacing-v1' "
            "WHERE algorithm_version IS NULL"
        )
    )
    rows = connection.execute(
        text("SELECT id, job_id FROM clips WHERE position IS NULL ORDER BY job_id, created_at, id")
    ).fetchall()
    positions: dict[str, int] = {}
    for clip_id, job_id in rows:
        positions[job_id] = positions.get(job_id, 0) + 1
        connection.execute(
            text("UPDATE clips SET position = :position WHERE id = :id"),
            {"position": positions[job_id], "id": clip_id},
        )


def _migration_003_campaigns(connection) -> None:
    """Campaigns with versioned configurations, plus job provenance columns."""
    from app.models import Campaign, CampaignConfiguration
    from app.services.campaigns import seed_preset_campaigns

    # Campaign is created first because ``jobs.campaign_id`` references it.
    Campaign.__table__.create(connection, checkfirst=True)
    CampaignConfiguration.__table__.create(connection, checkfirst=True)
    _add_missing_columns(
        connection,
        "jobs",
        {
            "campaign_id": "VARCHAR REFERENCES campaigns(id)",
            "campaign_configuration_version": "INTEGER",
        },
    )
    if "jobs" in inspect(connection).get_table_names():
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_campaign_id ON jobs (campaign_id)"))
    # Old jobs keep the brief embedded in ``processing_options``; they stay
    # unlinked (campaign_id NULL) rather than being guessed into a campaign.
    seed_preset_campaigns(connection)


MIGRATIONS = (
    (1, "v1_columns", _migration_001_v1_columns),
    (2, "candidate_review_and_edits", _migration_002_candidate_review_and_edits),
    (3, "campaigns", _migration_003_campaigns),
)


def _ensure_local_owner() -> None:
    """Give legacy jobs a stable owner while local auth remains disabled."""
    from app.models import Job, User

    with SessionLocal() as db:
        local_user = db.query(User).filter(User.username == "local").first()
        if local_user is None:
            local_user = User(
                id="local-user",
                username="local",
                display_name="Local User",
                password_hash=None,
            )
            db.add(local_user)
            db.flush()

        (
            db.query(Job)
            .filter(Job.owner_id.is_(None))
            .update({Job.owner_id: local_user.id}, synchronize_session=False)
        )
        db.commit()


ACTIVE_INTERRUPTIBLE_JOB_STATUSES = (
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


@dataclass(frozen=True)
class StartupRecoveryReport:
    pending_job_ids: tuple[str, ...] = ()
    retry_job_ids: tuple[str, ...] = ()
    failed_jobs: int = 0
    failed_clips: int = 0
    recovered_renders: int = 0


def recover_jobs_after_startup() -> StartupRecoveryReport:
    """
    Recover open jobs after backend startup.

    Pending jobs are safe to queue again because no pipeline stage has started.
    Jobs already inside a processing stage are not resumed automatically, because
    rerunning them in-place can duplicate clips or mix old/new artifacts. They are
    left failed and the user may explicitly create a linked retry from the UI.
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

        interrupted_jobs = (
            db.query(Job)
            .filter(Job.status.in_(ACTIVE_INTERRUPTIBLE_JOB_STATUSES))
            .all()
        )
        message = "Interrupted by backend restart while processing."
        retry_job_ids: list[str] = []
        for job in interrupted_jobs:
            job.status = "failed"
            job.error_code = "INTERRUPTED"
            job.error_message = message
            job.warning_message = "Jalankan ulang secara manual bila masih diperlukan."
            job.updated_at = now
            job.completed_at = now
            job.stage_started_at = None
            job.heartbeat_at = now

        failed_jobs = len(interrupted_jobs)

        failed_clips = 0
        if failed_jobs:
            interrupted_job_ids = [job.id for job in interrupted_jobs]
            failed_clips = (
                db.query(Clip)
                .filter(Clip.status == "processing", Clip.job_id.in_(interrupted_job_ids))
                .update({Clip.status: "failed"}, synchronize_session=False)
            )

        # A re-render (trim/export) of a clip on a finished job can be cut off
        # by a restart too. Keep the previous file when it still exists so the
        # clip stays usable, and record why the new render did not finish.
        orphaned_renders = (
            db.query(Clip)
            .join(Job, Clip.job_id == Job.id)
            .filter(Clip.status == "processing", Job.status.notin_(ACTIVE_INTERRUPTIBLE_JOB_STATUSES + ("pending",)))
            .all()
        )
        for clip in orphaned_renders:
            has_file = bool(clip.file_path) and Path(clip.file_path).exists()
            clip.status = "ready" if has_file else "failed"
            clip.render_error_code = "INTERRUPTED"
            clip.render_error_message = "Render terhenti karena backend restart. Jalankan render ulang."
            failed_clips += 0 if has_file else 1

        db.commit()
        return StartupRecoveryReport(
            pending_job_ids=pending_job_ids,
            retry_job_ids=tuple(retry_job_ids),
            failed_jobs=failed_jobs,
            failed_clips=failed_clips,
            recovered_renders=len(orphaned_renders),
        )


def mark_interrupted_jobs_failed() -> int:
    """Backward-compatible wrapper for older tests/tools."""
    return recover_jobs_after_startup().failed_jobs
