"""Local YouTube access gate that prevents repeat bot-block download jobs.

The gate never probes YouTube. It only validates that the locally configured
browser cookie file is present and remembers a bot/429 response observed by
the downloader. That keeps a pasted URL from generating another request while
the current session or IP is known to be blocked.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from loguru import logger

from app.config import settings


AccessStatus = Literal["ready", "cookies_missing", "cooldown"]


@dataclass(frozen=True)
class YouTubeAccessStatus:
    can_start: bool
    status: AccessStatus
    message: str
    retry_after_seconds: int
    cookies_ready: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "can_start": self.can_start,
            "status": self.status,
            "message": self.message,
            "retry_after_seconds": self.retry_after_seconds,
            "cookies_ready": self.cookies_ready,
        }


class YouTubeAccessBlocked(RuntimeError):
    """Raised before a YouTube request when local access is not ready."""

    def __init__(self, access_status: YouTubeAccessStatus):
        super().__init__(access_status.message)
        self.access_status = access_status

    @property
    def http_status_code(self) -> int:
        return 429 if self.access_status.status == "cooldown" else 409


def get_youtube_access_status(now: datetime | None = None) -> YouTubeAccessStatus:
    """Return a local readiness status without making any YouTube request."""
    now = _as_utc(now or _utc_now())
    cookie_fingerprint = _configured_cookie_fingerprint()
    cookies_ready = cookie_fingerprint is not None

    if settings.youtube_require_cookies and not cookies_ready:
        return YouTubeAccessStatus(
            can_start=False,
            status="cookies_missing",
            message=(
                "File cookies YouTube belum tersedia, kosong, atau tidak dapat diakses oleh server. "
                "Tambahkan file cookies Netscape yang valid pada lokasi YOUTUBE_COOKIES_PATH, "
                "lalu pilih Periksa ulang. Job belum dibuat."
            ),
            retry_after_seconds=0,
            cookies_ready=False,
        )

    state = _read_block_state()
    if state:
        blocked_cookie_fingerprint = state.get("cookie_fingerprint")
        # A user who exports a new browser session should be able to try it
        # immediately. We compare file metadata only; cookie contents never
        # enter logs, the API, or this state file.
        if blocked_cookie_fingerprint != cookie_fingerprint:
            _clear_block_state()
            logger.info("YouTube access hold cleared after local cookie file changed")
        else:
            blocked_until = _parse_time(state.get("blocked_until"))
            if blocked_until and blocked_until > now:
                retry_after_seconds = max(1, int((blocked_until - now).total_seconds()))
                return YouTubeAccessStatus(
                    can_start=False,
                    status="cooldown",
                    message=(
                        "YouTube sedang dijeda oleh ClipGen untuk mencegah blokir berulang. "
                        f"Coba lagi dalam {_format_wait(retry_after_seconds)}. "
                        "Cookie browser yang diekspor ulang akan membuka pemeriksaan ini lebih awal."
                    ),
                    retry_after_seconds=retry_after_seconds,
                    cookies_ready=cookies_ready,
                )

    return YouTubeAccessStatus(
        can_start=True,
        status="ready",
        message=(
            "Sesi YouTube lokal siap. ClipGen akan tetap menghentikan percobaan "
            "jika YouTube mengirim bot-block."
            if cookies_ready
            else "Cookie tidak diwajibkan oleh konfigurasi lokal ini."
        ),
        retry_after_seconds=0,
        cookies_ready=cookies_ready,
    )


def require_youtube_access() -> None:
    """Raise a user-safe error before a job enters the queue or downloads."""
    access_status = get_youtube_access_status()
    if not access_status.can_start:
        raise YouTubeAccessBlocked(access_status)


def record_youtube_bot_block(
    cookies_path: Path | str | None = None,
    now: datetime | None = None,
) -> YouTubeAccessStatus:
    """Persist a bounded exponential cooldown after a real 429/bot response."""
    now = _as_utc(now or _utc_now())
    previous = _read_block_state()
    previous_blocked_at = _parse_time(previous.get("blocked_at")) if previous else None
    prior_count = int(previous.get("consecutive_blocks", 0)) if previous else 0
    max_cooldown = max(
        settings.youtube_bot_block_cooldown_seconds,
        settings.youtube_bot_block_max_cooldown_seconds,
    )
    # Only escalate consecutive blocks that occur within the current recovery
    # window. A much later independent block starts again at the base delay.
    if previous_blocked_at and (now - previous_blocked_at).total_seconds() <= max_cooldown:
        consecutive_blocks = max(1, prior_count + 1)
    else:
        consecutive_blocks = 1

    delay_seconds = min(
        max_cooldown,
        settings.youtube_bot_block_cooldown_seconds * (2 ** (consecutive_blocks - 1)),
    )
    blocked_until = now + timedelta(seconds=delay_seconds)
    active_cookies_path = settings.youtube_cookies_path if cookies_path is None else cookies_path
    _write_block_state(
        {
            "version": 1,
            "blocked_at": now.isoformat(),
            "blocked_until": blocked_until.isoformat(),
            "consecutive_blocks": consecutive_blocks,
            "cookie_fingerprint": _cookie_fingerprint(active_cookies_path),
        }
    )
    logger.warning(
        "YouTube bot-block recorded; holding new downloads for {} seconds (block #{})",
        delay_seconds,
        consecutive_blocks,
    )
    return get_youtube_access_status(now=now)


def clear_youtube_bot_block() -> None:
    """Clear an old hold only after a real successful YouTube download."""
    if _state_path().exists():
        _clear_block_state()
        logger.info("YouTube access hold cleared after successful download")


def _configured_cookie_fingerprint() -> str | None:
    return _cookie_fingerprint(settings.youtube_cookies_path)


def _cookie_fingerprint(cookies_path: Path | str | None) -> str | None:
    if cookies_path is None:
        return None
    raw_path = str(cookies_path).strip()
    if not raw_path or raw_path == ".":
        return None
    try:
        stat = Path(raw_path).stat()
    except OSError:
        return None
    if not Path(raw_path).is_file() or stat.st_size <= 0:
        return None
    # Deliberately metadata-only: never persist browser session data.
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _state_path() -> Path:
    return settings.storage_dir / "youtube_access_state.json"


def _read_block_state() -> dict[str, object]:
    try:
        parsed = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _write_block_state(state: dict[str, object]) -> None:
    state_path = _state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_suffix(".tmp")
    try:
        temporary_path.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
        temporary_path.replace(state_path)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)
        logger.warning("Unable to persist YouTube access hold: {}", error)


def _clear_block_state() -> None:
    try:
        _state_path().unlink(missing_ok=True)
    except OSError as error:
        logger.warning("Unable to clear YouTube access hold: {}", error)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_wait(seconds: int) -> str:
    if seconds < 60:
        return "kurang dari 1 menit"
    minutes = (seconds + 59) // 60
    if minutes < 60:
        return f"sekitar {minutes} menit"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"sekitar {hours} jam" + (f" {remaining_minutes} menit" if remaining_minutes else "")
