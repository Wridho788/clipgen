from datetime import datetime, timedelta, timezone

import pytest

from app.api.routes.videos import youtube_preflight
from app.config import settings
from app.models import User
from app.services import youtube_access


@pytest.fixture
def youtube_access_files(monkeypatch, tmp_path):
    cookie_file = tmp_path / "youtube-cookies.txt"
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    monkeypatch.setattr(settings, "youtube_cookies_path", str(cookie_file))
    monkeypatch.setattr(settings, "youtube_require_cookies", True)
    monkeypatch.setattr(settings, "youtube_bot_block_cooldown_seconds", 60)
    monkeypatch.setattr(settings, "youtube_bot_block_max_cooldown_seconds", 240)
    return cookie_file


def test_preflight_blocks_missing_cookie_before_a_job_can_start(youtube_access_files):
    status = youtube_access.get_youtube_access_status()

    assert status.can_start is False
    assert status.status == "cookies_missing"
    assert status.cookies_ready is False
    with pytest.raises(youtube_access.YouTubeAccessBlocked):
        youtube_access.require_youtube_access()


def test_bot_block_uses_cooldown_and_new_cookie_file_clears_it(youtube_access_files):
    youtube_access_files.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    now = datetime(2026, 9, 13, 9, 0, tzinfo=timezone.utc)

    first_hold = youtube_access.record_youtube_bot_block(now=now)
    assert first_hold.status == "cooldown"
    assert first_hold.retry_after_seconds == 60

    second_hold = youtube_access.record_youtube_bot_block(now=now + timedelta(seconds=1))
    assert second_hold.status == "cooldown"
    assert second_hold.retry_after_seconds == 120

    # File metadata changes without ever reading or storing its sensitive data.
    youtube_access_files.write_text("# Netscape HTTP Cookie File\n# refreshed\n", encoding="utf-8")
    refreshed = youtube_access.get_youtube_access_status(now=now + timedelta(seconds=2))

    assert refreshed.can_start is True
    assert refreshed.status == "ready"
    assert not (settings.storage_dir / "youtube_access_state.json").exists()


@pytest.mark.asyncio
async def test_preflight_route_reports_only_safe_local_readiness(youtube_access_files):
    response = await youtube_preflight(
        current_user=User(id="user-1", username="tester", display_name="Tester"),
    )

    assert response["can_start"] is False
    assert response["status"] == "cookies_missing"
    assert response["cookies_ready"] is False
    assert "cookies" in response["message"].lower()
