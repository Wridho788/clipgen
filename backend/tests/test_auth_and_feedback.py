import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import auth, clips
from app.config import settings
from app.models import Base, Clip, Job, User
from app.schemas import AuthLoginRequest, AuthRegisterRequest, ClipFeedbackRequest


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.mark.asyncio
async def test_local_auth_registers_and_logs_in(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret")
    Session = _session(tmp_path)
    with Session() as db:
        registered = await auth.register(
            AuthRegisterRequest(username="editor", password="very-safe-pass", display_name="Video Editor"),
            db,
        )
        logged_in = await auth.login(AuthLoginRequest(username="editor", password="very-safe-pass"), db)

    assert registered.user.username == "editor"
    assert logged_in.access_token


@pytest.mark.asyncio
async def test_clip_feedback_is_scoped_to_clip_owner(tmp_path):
    Session = _session(tmp_path)
    with Session() as db:
        user = User(id="user-1", username="editor", display_name="Editor")
        job = Job(id="job-1", owner_id=user.id, source_type="upload", source_path="/tmp/video.mp4", status="done")
        clip = Clip(id="clip-1", job_id=job.id, start_time=0, end_time=15, highlight_score=1, status="ready")
        db.add_all([user, job, clip])
        db.commit()

        positive = await clips.rate_clip("clip-1", ClipFeedbackRequest(rating=1), db, user)
        negative = await clips.rate_clip("clip-1", ClipFeedbackRequest(rating=-1, reason="intro"), db, user)

    assert positive.positive_count == 1
    assert negative.rating == -1
    assert negative.positive_count == 0
    assert negative.negative_count == 1
