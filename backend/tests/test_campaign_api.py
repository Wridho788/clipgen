"""Campaign endpoints through the real ASGI stack."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_current_user
from app.database import get_db, run_migrations
from app.main import app
from app.models import Base, User
from asgi_client import call  # tests/ is on sys.path (pytest prepend import mode)


@pytest.fixture
def api(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session = sessionmaker(bind=engine)()
    user = User(id="u1", username="editor", display_name="Editor")
    api_app = getattr(app, "app", app)
    monkeypatch.setitem(api_app.dependency_overrides, get_db, lambda: session)
    monkeypatch.setitem(api_app.dependency_overrides, get_current_user, lambda: user)
    yield session
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_presets_are_listed_as_campaigns_and_legacy_endpoint_still_works(api):
    status, _, campaigns = await call("GET", "/api/campaigns")
    assert status == 200
    assert {item["id"] for item in campaigns} == {"preset-rumah_ningrat", "preset-yava_happy_health"}

    status, _, presets = await call("GET", "/api/campaigns/presets")
    assert status == 200 and len(presets) == 2


@pytest.mark.asyncio
async def test_edit_creates_new_version_and_old_version_stays_readable(api):
    status, _, created = await call(
        "POST", "/api/campaigns", json={"name": "Promo", "config": {"rules": {"max_clip_seconds": 90}}}
    )
    assert status == 201
    assert (created["latest_version"], created["confirmed"]) == (1, False)
    campaign_id = created["id"]

    status, _, updated = await call(
        "PUT", f"/api/campaigns/{campaign_id}",
        json={"config": {"rules": {"max_clip_seconds": 45}}, "confirmed": True},
    )
    assert status == 200
    assert (updated["latest_version"], updated["confirmed"]) == (2, True)

    _, _, versions = await call("GET", f"/api/campaigns/{campaign_id}/versions")
    assert [item["config"]["rules"]["max_clip_seconds"] for item in versions] == [90.0, 45.0]
    status, _, first = await call("GET", f"/api/campaigns/{campaign_id}/versions/1")
    assert status == 200 and first["config"]["rules"]["max_clip_seconds"] == 90.0


@pytest.mark.asyncio
async def test_invalid_config_and_unknown_campaign_are_rejected(api):
    status, _, _ = await call(
        "POST", "/api/campaigns",
        json={"name": "Bad", "config": {"rules": {"min_clip_seconds": 100, "max_clip_seconds": 10}}},
    )
    assert status == 422
    status, _, body = await call("GET", "/api/campaigns/missing")
    assert status == 404 and "tidak ditemukan" in body["detail"]


@pytest.mark.asyncio
async def test_duplicate_and_archive_flow(api):
    _, _, created = await call("POST", "/api/campaigns", json={"name": "Promo", "config": {}})
    campaign_id = created["id"]

    status, _, copy = await call("POST", f"/api/campaigns/{campaign_id}/duplicate")
    assert status == 201 and copy["name"] == "Promo (salinan)" and copy["latest_version"] == 1

    status, _, archived = await call("POST", f"/api/campaigns/{campaign_id}/archive")
    assert status == 200 and archived["status"] == "archived"
    status, _, body = await call("PUT", f"/api/campaigns/{campaign_id}", json={"config": {}})
    assert status == 409
    _, _, active = await call("GET", "/api/campaigns")
    assert campaign_id not in [item["id"] for item in active]
    _, _, everything = await call("GET", "/api/campaigns?include_archived=true")
    assert campaign_id in [item["id"] for item in everything]

    status, _, restored = await call("POST", f"/api/campaigns/{campaign_id}/unarchive")
    assert status == 200 and restored["status"] == "active"


@pytest.mark.asyncio
async def test_analyze_returns_a_draft_and_saves_nothing(api):
    _, _, before = await call("GET", "/api/campaigns?include_archived=true")

    status, _, draft = await call(
        "POST", "/api/campaigns/analyze",
        json={"text": "Campaign Promo\nDurasi 30-60 detik. Wajib #Promo di TikTok."},
    )

    assert status == 200
    assert draft["fields"]["min_clip_seconds"]["value"] == 30.0
    assert draft["fields"]["hashtags"]["value"] == ["Promo"]
    assert draft["fields"]["platforms"]["value"] == ["tiktok"]
    assert draft["fields"]["cta"]["status"] == "not_provided"
    assert draft["raw_source_text"].startswith("Campaign Promo")
    _, _, after = await call("GET", "/api/campaigns?include_archived=true")
    assert after == before


@pytest.mark.asyncio
async def test_analyze_rejects_blank_text_with_a_readable_422(api):
    status, _, body = await call("POST", "/api/campaigns/analyze", json={"text": "   "})

    assert status == 422
    assert "kosong" in body["detail"]


@pytest.mark.asyncio
async def test_analyze_rejects_absurdly_large_payloads(api):
    status, _, _ = await call("POST", "/api/campaigns/analyze", json={"text": "x" * 500_001})

    assert status == 422
