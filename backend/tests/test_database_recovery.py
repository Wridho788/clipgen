from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Clip, Job


def test_recover_jobs_after_startup_requeues_pending_and_requires_manual_retry_for_active(monkeypatch, tmp_path):
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'app.db'}",
        connect_args={"check_same_thread": False},
    )
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", test_session)

    Base.metadata.create_all(bind=test_engine)
    database.init_db()

    with test_session() as db:
        pending = Job(
            id="pending-job",
            source_type="upload",
            source_path="/tmp/pending.mp4",
            status="pending",
            progress=0,
            error_message="old transient error",
        )
        interrupted = Job(
            id="interrupted-job",
            source_type="upload",
            source_path="/tmp/input.mp4",
            status="transcribing",
            progress=30,
        )
        completed = Job(
            id="completed-job",
            source_type="upload",
            source_path="/tmp/done.mp4",
            status="done",
            progress=100,
        )
        processing_clip = Clip(
            id="processing-clip",
            job_id="interrupted-job",
            start_time=0,
            end_time=10,
            highlight_score=1,
            status="processing",
        )
        ready_clip = Clip(
            id="ready-clip",
            job_id="completed-job",
            start_time=0,
            end_time=10,
            highlight_score=1,
            status="ready",
        )
        db.add_all([pending, interrupted, completed, processing_clip, ready_clip])
        db.commit()

    report = database.recover_jobs_after_startup()

    with test_session() as db:
        pending_job = db.get(Job, "pending-job")
        interrupted_job = db.get(Job, "interrupted-job")

        assert report.pending_job_ids == ("pending-job",)
        assert report.failed_jobs == 1
        assert report.retry_job_ids == ()
        assert report.failed_clips == 1
        assert pending_job.status == "pending"
        assert pending_job.error_message is None
        assert interrupted_job.status == "failed"
        assert interrupted_job.error_message
        assert interrupted_job.warning_message == "Jalankan ulang secara manual bila masih diperlukan."
        assert interrupted_job.completed_at is not None
        assert db.get(Job, "completed-job").status == "done"
        assert db.get(Clip, "processing-clip").status == "failed"
        assert db.get(Clip, "ready-clip").status == "ready"
