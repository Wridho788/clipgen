"""Jobs created from a saved campaign pin its version and keep a brief snapshot."""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import jobs, videos
from app.core.security import get_current_user
from app.database import get_db, run_migrations
from app.main import app
from app.models import Base, Job, User
from app.schemas import CampaignBrief, CampaignConfigData
from app.services import campaigns as campaign_service
from app.services.media_probe import VideoInfo
from asgi_client import call
from test_upload_reliability import request  # multipart-capable ASGI helper


def _multipart(**fields) -> bytes:
    body = b""
    for name, value in fields.items():
        body += f'--upload-test\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    body += (
        b'--upload-test\r\nContent-Disposition: form-data; name="file"; filename="video.mp4"'
        b"\r\nContent-Type: video/mp4\r\n\r\nvideo\r\n--upload-test--\r\n"
    )
    return body


def _config(max_seconds: int) -> CampaignConfigData:
    return CampaignConfigData(rules=CampaignBrief(min_clip_seconds=20, max_clip_seconds=max_seconds))


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session = sessionmaker(bind=engine)()
    user = User(id="u1", username="u", display_name="U")
    session.add(user)
    session.commit()
    campaign = campaign_service.create_campaign(
        session, owner_id="u1", name="Promo", campaign_type="custom", source="user_created",
        config=_config(60),
    )
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(videos.settings, "upload_dir", upload_dir)
    monkeypatch.setattr(videos, "probe_video", lambda path: VideoInfo(60, 1920, 1080))
    monkeypatch.setattr(videos, "has_audio_stream", lambda path: True)
    monkeypatch.setattr(videos, "calibrate_stage_estimates", lambda db, source, stages: (stages, {}))

    async def enqueue(job_id):
        return None

    monkeypatch.setattr(videos, "enqueue_job", enqueue)
    monkeypatch.setattr(jobs, "enqueue_job", enqueue)
    api_app = getattr(app, "app", app)
    monkeypatch.setitem(api_app.dependency_overrides, get_db, lambda: session)
    monkeypatch.setitem(api_app.dependency_overrides, get_current_user, lambda: user)
    yield session, campaign, upload_dir, tmp_path
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_upload_with_campaign_pins_version_and_snapshots_the_brief(workspace):
    db, campaign, _, _ = workspace

    status, _, payload = await request(
        "/api/videos/upload", _multipart(campaign_id=campaign.id)
    )

    assert status == 200
    job = db.get(Job, payload["job_id"])
    assert (job.campaign_id, job.campaign_configuration_version) == (campaign.id, 1)
    snapshot = json.loads(job.processing_options)["campaign_brief"]
    assert (snapshot["id"], snapshot["name"], snapshot["max_clip_seconds"]) == (campaign.id, "Promo", 60.0)

    # A later campaign edit must not reach back into the job that already ran.
    campaign_service.add_configuration_version(db, campaign.id, "u1", _config(90))
    db.expire_all()
    job = db.get(Job, payload["job_id"])
    assert job.campaign_configuration_version == 1
    assert json.loads(job.processing_options)["campaign_brief"]["max_clip_seconds"] == 60.0


@pytest.mark.asyncio
async def test_upload_can_pin_an_older_configuration_version(workspace):
    db, campaign, _, _ = workspace
    campaign_service.add_configuration_version(db, campaign.id, "u1", _config(90))

    status, _, payload = await request(
        "/api/videos/upload", _multipart(campaign_id=campaign.id, campaign_configuration_version=1)
    )

    assert status == 200
    job = db.get(Job, payload["job_id"])
    assert job.campaign_configuration_version == 1
    assert json.loads(job.processing_options)["campaign_brief"]["max_clip_seconds"] == 60.0


@pytest.mark.asyncio
async def test_upload_for_unknown_campaign_fails_before_storing_anything(workspace):
    db, _, upload_dir, _ = workspace

    status, _, payload = await request("/api/videos/upload", _multipart(campaign_id="nope"))

    assert status == 404
    assert db.query(Job).count() == 0
    assert list(upload_dir.iterdir()) == []


def _finished_job(db, tmp_path, campaign, brief_max=60):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    brief = CampaignBrief(id=campaign.id, name="Promo", min_clip_seconds=20, max_clip_seconds=brief_max)
    options = {"min_clip_seconds": 20, "max_clip_seconds": brief_max, "campaign_brief": brief.model_dump()}
    job = Job(
        id="job-1", owner_id="u1", source_type="upload", source_path=str(source), source_name="v.mp4",
        source_duration_seconds=60.0, status="done", progress=100,
        processing_options=json.dumps(options),
        campaign_id=campaign.id, campaign_configuration_version=1,
    )
    db.add(job)
    db.commit()
    return job


@pytest.mark.asyncio
async def test_retry_keeps_the_campaign_link_while_the_brief_is_unchanged(workspace):
    db, campaign, _, tmp_path = workspace
    _finished_job(db, tmp_path, campaign)

    status, _, payload = await call("POST", "/api/jobs/job-1/retry")

    assert status == 200
    retry = db.get(Job, payload["job_id"])
    assert (retry.campaign_id, retry.campaign_configuration_version) == (campaign.id, 1)


@pytest.mark.asyncio
async def test_retry_with_a_different_brief_drops_the_campaign_link(workspace):
    db, campaign, _, tmp_path = workspace
    _finished_job(db, tmp_path, campaign)
    override = {"processing_options": {"min_clip_seconds": 10, "max_clip_seconds": 30}}

    status, _, payload = await call("POST", "/api/jobs/job-1/retry", json=override)

    assert status == 200
    retry = db.get(Job, payload["job_id"])
    assert (retry.campaign_id, retry.campaign_configuration_version) == (None, None)
