"""Exercise upload failures through the ASGI boundary without a live server."""
import asyncio
import json
import subprocess
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import videos
from app.core.security import get_current_user
from app.database import get_db
from app.main import app
from app.models import Base, Job, User
from app.services.media_probe import VideoInfo


async def request(path, body=b"", origin="http://localhost:3000"):
    messages = []
    received = False
    complete = asyncio.Event()

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body, "more_body": False}
        await complete.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            complete.set()

    headers = [(b"origin", origin.encode())]
    if body:
        headers.append((b"content-type", b"multipart/form-data; boundary=upload-test"))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST" if body else "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": headers, "client": ("127.0.0.1", 1234), "server": ("test", 80),
    }
    try:
        await app(scope, receive, send)
    except Exception:
        # ServerErrorMiddleware re-raises after sending an unhandled 500.
        if not any(m["type"] == "http.response.start" for m in messages):
            raise
    start = next(m for m in messages if m["type"] == "http.response.start")
    payload = b"".join(m.get("body", b"") for m in messages)
    return start["status"], dict(start["headers"]), json.loads(payload)


UPLOAD_BODY = (
    b'--upload-test\r\nContent-Disposition: form-data; name="file"; filename="video.mp4"'
    b'\r\nContent-Type: video/mp4\r\n\r\nvideo\r\n--upload-test--\r\n'
)


@pytest.fixture
def intake(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(id="upload-user", username="upload", display_name="Upload")
    session.add(user)
    session.commit()
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(videos.settings, "upload_dir", upload_dir)
    monkeypatch.setattr(videos, "probe_video", lambda path: VideoInfo(60, 1920, 1080))
    monkeypatch.setattr(videos, "has_audio_stream", lambda path: True)
    monkeypatch.setattr(videos, "calibrate_stage_estimates", lambda db, source, stages: (stages, {}))
    queued = []

    async def enqueue(job_id):
        queued.append(job_id)

    monkeypatch.setattr(videos, "enqueue_job", enqueue)
    api_app = getattr(app, "app", app)
    monkeypatch.setitem(api_app.dependency_overrides, get_db, lambda: session)
    monkeypatch.setitem(api_app.dependency_overrides, get_current_user, lambda: user)
    yield session, upload_dir, queued
    session.close()
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("probe", ["probe_video", "has_audio_stream"])
async def test_upload_timeout_has_readable_error_and_removes_unqueued_file(intake, monkeypatch, probe):
    def timeout(path):
        raise subprocess.TimeoutExpired("ffprobe", 60)

    monkeypatch.setattr(videos, probe, timeout)
    status, headers, payload = await request("/api/videos/upload", UPLOAD_BODY)
    db, upload_dir, queued = intake
    assert status == 504
    assert headers[b"access-control-allow-origin"] == b"http://localhost:3000"
    assert "pemeriksaan" in payload["detail"].lower()
    assert "corrupt" not in payload["detail"]
    assert list(upload_dir.iterdir()) == []
    assert db.query(Job).count() == 0
    assert queued == []


@pytest.mark.asyncio
async def test_upload_probes_run_off_event_loop_and_valid_file_is_queued(intake, monkeypatch):
    event_loop_thread = threading.get_ident()
    probe_threads = []

    def video(path):
        probe_threads.append(threading.get_ident())
        return VideoInfo(60, 1920, 1080)

    def audio(path):
        probe_threads.append(threading.get_ident())
        return True

    monkeypatch.setattr(videos, "probe_video", video)
    monkeypatch.setattr(videos, "has_audio_stream", audio)
    status, _, payload = await request("/api/videos/upload", UPLOAD_BODY)
    db, upload_dir, queued = intake
    assert status == 200
    assert queued == [payload["job_id"]]
    assert db.query(Job).count() == 1
    assert len(list(upload_dir.iterdir())) == 1
    assert len(probe_threads) == 2
    assert all(thread != event_loop_thread for thread in probe_threads)


@pytest.mark.asyncio
@pytest.mark.parametrize("origin,allowed", [("http://localhost:3000", True), ("https://untrusted.example", False)])
async def test_unhandled_upload_error_preserves_cors_policy(intake, monkeypatch, origin, allowed):
    def unexpected_error(path):
        raise RuntimeError("private diagnostic must not reach the browser")

    monkeypatch.setattr(videos, "probe_video", unexpected_error)
    status, headers, payload = await request("/api/videos/upload", UPLOAD_BODY, origin)
    assert status == 500
    assert (b"access-control-allow-origin" in headers) is allowed
    assert payload == {"detail": "Internal server error"}


@pytest.mark.asyncio
@pytest.mark.parametrize("probe,value", [("probe_video", None), ("has_audio_stream", False)])
async def test_invalid_media_is_rejected_without_a_job(intake, monkeypatch, probe, value):
    monkeypatch.setattr(videos, probe, lambda path: value)
    status, _, _ = await request("/api/videos/upload", UPLOAD_BODY)
    db, upload_dir, queued = intake
    assert status == 400
    assert db.query(Job).count() == 0
    assert list(upload_dir.iterdir()) == []
    assert queued == []


@pytest.mark.asyncio
async def test_health_still_works_with_outer_cors():
    for path in ("/health", "/health/live"):
        status, headers, payload = await request(path)
        assert status == 200
        assert payload["status"] == "ok"
        assert payload["version"]
        assert headers[b"access-control-allow-origin"] == b"http://localhost:3000"
