"""Clip review/edit/render endpoints through the real ASGI stack."""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import clips as clip_routes
from app.core.edit_model import CaptionCue, default_edit
from app.core.security import get_current_user
from app.database import get_db
from app.main import app
from app.models import Base, Clip, Job, User
from asgi_client import call  # tests/ is on sys.path (pytest prepend import mode)


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(id="u1", username="editor", display_name="Editor")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"0123456789" * 100)
    job = Job(
        id="job-1", owner_id="u1", source_type="upload", source_path=str(source), source_name="talk.mp4",
        source_duration_seconds=100.0, status="done", progress=100,
        processing_options=json.dumps({"output_preset": "tiktok", "visual_style": "crop", "min_clip_seconds": 10,
                                       "max_clip_seconds": 60}),
        transcript_json=json.dumps([{"start": 10.0, "end": 14.0, "text": "hello there world"}]),
    )
    clip_files = []
    session.add_all([user, job])
    for index in range(2):
        clip_file = tmp_path / f"clip{index}.mp4"
        clip_file.write_bytes(b"clipdata" * 50)
        clip_files.append(clip_file)
        edit = default_edit(
            start_ms=10_000 + index * 30_000, end_ms=30_000 + index * 30_000, output_preset="tiktok",
            visual_style="crop", captions_enabled=True,
            cues=[CaptionCue(start_ms=10_000, end_ms=12_000, text="hello there", original_text="hello there")],
        )
        session.add(Clip(
            id=f"clip-{index}", job_id="job-1", start_time=10.0 + index * 30, end_time=30.0 + index * 30,
            suggested_start_time=10.0 + index * 30, suggested_end_time=30.0 + index * 30,
            highlight_score=0.5, status="ready", file_path=str(clip_file), position=index + 1,
            edit_json=edit.model_dump_json(), edit_revision=1, rendered_revision=1,
            algorithm_version="transcript-boundary-v1",
            analysis_json=json.dumps({"rank": index + 1, "total": 2, "score": 0.9, "explanation": ["x"], "signals": {}}),
        ))
    session.commit()
    monkeypatch.setattr(clip_routes.settings, "clips_dir", tmp_path)
    queued = []

    async def enqueue(clip_id):
        queued.append(clip_id)

    monkeypatch.setattr(clip_routes, "enqueue_clip_render", enqueue)
    api_app = getattr(app, "app", app)
    monkeypatch.setitem(api_app.dependency_overrides, get_db, lambda: session)
    monkeypatch.setitem(api_app.dependency_overrides, get_current_user, lambda: user)
    yield session, queued, clip_files
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_clip_response_exposes_candidate_edit_and_render_state(workspace):
    status, _, body = await call("GET", "/api/clips/clip-0")
    assert status == 200
    assert body["candidate"]["rank"] == 1
    assert "score" not in body["candidate"]  # raw internal score is not shown
    assert "bukan prediksi" in body["candidate"]["score_meaning"]
    assert body["edit"]["trim_start_ms"] == 10_000
    assert body["edit_revision"] == 1 and body["render_stale"] is False
    assert body["review_status"] == "suggested"
    assert body["suggested_start_time"] == 10.0


@pytest.mark.asyncio
async def test_autosave_edit_bumps_revision_and_marks_render_stale(workspace):
    session, queued, _ = workspace
    _, _, clip = await call("GET", "/api/clips/clip-0")
    edit = clip["edit"]
    edit["trim_start_ms"] = 11_500
    edit["captions"]["cues"][0]["text"] = "hello their"
    edit["captions"]["style"]["text_color"] = "#ffcc00"

    status, _, body = await call("PUT", "/api/clips/clip-0/edit", json={"base_revision": 1, "edit": edit})

    assert status == 200
    assert body["edit_revision"] == 2
    assert body["render_stale"] is True
    assert body["start_time"] == 11.5
    assert body["review_status"] == "edited"
    assert body["edit"]["captions"]["style"]["text_color"] == "#FFCC00"
    assert body["edit"]["captions"]["cues"][0]["original_text"] == "hello there"
    assert queued == []  # saving never renders implicitly


@pytest.mark.asyncio
async def test_stale_autosave_is_rejected_with_conflict_code(workspace):
    _, _, clip = await call("GET", "/api/clips/clip-0")
    await call("PUT", "/api/clips/clip-0/edit", json={"base_revision": 1, "edit": clip["edit"]})
    status, _, body = await call("PUT", "/api/clips/clip-0/edit", json={"base_revision": 1, "edit": clip["edit"]})
    assert status == 409
    assert body["code"] == "EDIT_CONFLICT"


@pytest.mark.asyncio
async def test_edit_beyond_source_duration_is_rejected(workspace):
    _, _, clip = await call("GET", "/api/clips/clip-0")
    edit = clip["edit"] | {"trim_start_ms": 90_000, "trim_end_ms": 110_000}
    status, _, body = await call("PUT", "/api/clips/clip-0/edit", json={"base_revision": 1, "edit": edit})
    assert status == 422
    assert body["code"] == "EDIT_INVALID"
    assert "melebihi" in body["detail"]


@pytest.mark.asyncio
async def test_invalid_edit_payload_is_rejected_by_schema(workspace):
    _, _, clip = await call("GET", "/api/clips/clip-0")
    edit = clip["edit"] | {"trim_end_ms": 11_000}
    status, _, _ = await call("PUT", "/api/clips/clip-0/edit", json={"base_revision": 1, "edit": edit})
    assert status == 422


@pytest.mark.asyncio
async def test_review_requires_reason_to_reject(workspace):
    status, _, body = await call("POST", "/api/clips/clip-0/review", json={"status": "rejected"})
    assert status == 422 and body["code"] == "EDIT_INVALID"
    status, _, body = await call("POST", "/api/clips/clip-0/review", json={"status": "rejected", "reason": "bad_boundaries"})
    assert status == 200
    assert body["review_status"] == "rejected" and body["review_reason"] == "bad_boundaries"
    status, _, body = await call("POST", "/api/clips/clip-0/review", json={"status": "accepted"})
    assert body["review_status"] == "accepted" and body["review_reason"] is None


@pytest.mark.asyncio
async def test_render_queues_saved_revision_and_blocks_duplicates(workspace):
    session, queued, _ = workspace
    status, _, body = await call("POST", "/api/clips/clip-0/render")
    assert status == 202 and body["status"] == "processing"
    assert queued == ["clip-0"]
    status, _, _ = await call("POST", "/api/clips/clip-0/render")
    assert status == 409


@pytest.mark.asyncio
async def test_trim_route_updates_edit_document(workspace):
    session, queued, _ = workspace
    status, _, body = await call("POST", "/api/clips/clip-0/trim", json={"start_time": 12.0, "end_time": 40.0})
    assert status == 202
    assert body["edit"]["trim_start_ms"] == 12_000 and body["edit"]["trim_end_ms"] == 40_000
    assert body["edit_revision"] == 2
    assert queued == ["clip-0"]


@pytest.mark.asyncio
async def test_reorder_and_duplicate_preserve_a_complete_order(workspace):
    session, _, _ = workspace
    status, _, body = await call("POST", "/api/clips/job/job-1/order", json={"clip_ids": ["clip-1", "clip-0"]})
    assert status == 200
    assert [clip["id"] for clip in body] == ["clip-1", "clip-0"]
    status, _, _ = await call("POST", "/api/clips/job/job-1/order", json={"clip_ids": ["clip-1"]})
    assert status == 422

    status, _, copy = await call("POST", "/api/clips/clip-1/duplicate")
    assert status == 201
    assert copy["id"] not in {"clip-0", "clip-1"}
    assert copy["edit"]["trim_start_ms"] == 40_000
    assert copy["file_path"].endswith(f"{copy['id']}_r1.mp4")
    _, _, listed = await call("GET", "/api/clips/job/job-1")
    assert [clip["id"] for clip in listed] == ["clip-1", copy["id"], "clip-0"]


@pytest.mark.asyncio
async def test_download_marks_exported_and_preview_supports_ranges(workspace):
    status, headers, data = await call("GET", "/api/clips/clip-0/preview", headers={"Range": "bytes=0-9"})
    assert status == 206
    assert headers["content-range"] == "bytes 0-9/400"
    assert data == b"clipdataclip"[:10]
    status, headers, _ = await call("GET", "/api/clips/clip-0/source", headers={"Range": "bytes=-5"})
    assert status == 206 and headers["content-range"] == "bytes 995-999/1000"

    status, _, _ = await call("GET", "/api/clips/clip-0/file")
    assert status == 200
    _, _, clip = await call("GET", "/api/clips/clip-0")
    assert clip["review_status"] == "exported" and clip["exported_at"]


@pytest.mark.asyncio
async def test_unsatisfiable_range_returns_416(workspace):
    status, headers, _ = await call("GET", "/api/clips/clip-0/preview", headers={"Range": "bytes=999-1000"})
    assert status == 416
