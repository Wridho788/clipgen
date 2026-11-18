"""yt-dlp integration with retries and user-safe YouTube error messages."""
import subprocess
from pathlib import Path

from loguru import logger

from app.services.youtube_access import clear_youtube_bot_block, record_youtube_bot_block


class YouTubeDownloadError(RuntimeError):
    """Download failed after yt-dlp's normal and fallback attempts."""


def download_youtube_video(
    url: str,
    output_dir: Path,
    job_id: str,
    timeout_seconds: int,
    concurrent_fragments: int = 4,
    max_height: int = 720,
    cookies_path: Path | str | None = None,
    user_agent: str | None = None,
) -> Path:
    output_template = output_dir / f"{job_id}.%(ext)s"
    # A 403 often belongs to one playback client rather than the public video
    # itself.  Do not use web_safari as the sole fallback: recent YouTube
    # experiments can return 403 for its stream URLs.  The variants below use
    # only documented yt-dlp clients and progressively reduce request pressure.
    attempts = [
        ("default", None, concurrent_fragments),
        ("web_without_visionos", "youtube:player_client=default,-visionos", concurrent_fragments),
        ("web_embedded", "youtube:player_client=web_embedded,web", 1),
    ]
    errors = []
    format_selector = _build_format_selector(max_height)
    cookie_file = _usable_cookie_file(cookies_path)

    for attempt_name, extractor_args, attempt_fragments in attempts:
        cmd = [
            "yt-dlp",
            # This app pins yt-dlp in requirements.txt and updates it during a
            # deliberate image rebuild. Avoid leaking its update notice into a
            # user-facing download failure.
            "--no-update",
            "--no-playlist",
            "--no-progress",
            "--retries", "3",
            "--fragment-retries", "3",
            "--concurrent-fragments", str(attempt_fragments),
            "--http-chunk-size", "10M",
            "--merge-output-format", "mp4",
            "--write-info-json",
            "--print", "after_move:filepath",
            "--js-runtimes", "deno",
            "-f", format_selector,
            "-o", str(output_template),
        ]
        if extractor_args:
            cmd.extend(["--extractor-args", extractor_args])
        if cookie_file:
            cmd.extend(["--cookies", str(cookie_file)])
        if user_agent and user_agent.strip():
            cmd.extend(["--user-agent", user_agent.strip()])
        cmd.append(url)

        logger.info(
            f"YouTube download attempt for job {job_id}, client={attempt_name}, "
            f"fragments={attempt_fragments}, cookies={bool(cookie_file)}"
        )
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            errors.append("Download mencapai batas waktu")
            logger.warning(f"YouTube download timed out for job {job_id}: {error}")
            continue

        if result.returncode == 0:
            downloaded_path = _find_downloaded_path(result.stdout, output_dir, job_id)
            if downloaded_path:
                clear_youtube_bot_block()
                return downloaded_path
            errors.append("yt-dlp selesai tetapi file output tidak ditemukan")
            continue

        detail = (result.stderr or result.stdout).strip()
        errors.append(detail[-600:])
        logger.warning(f"yt-dlp attempt failed for job {job_id}: {detail[-600:]}")
        # A 429/bot challenge is generally scoped to the current IP/session.
        # Extra playback clients cannot solve it and only add requests, even
        # when an expired or rejected cookie was supplied. Persist a local
        # hold so future jobs are stopped before touching YouTube.
        if _is_rate_limited_or_bot_block(detail):
            record_youtube_bot_block(cookies_path=cookie_file)
            logger.warning(
                f"YouTube rate-limit/bot block for job {job_id}; stopping fallback attempts"
            )
            break
        if not _should_retry_with_fallback(detail):
            break

    _delete_partial_downloads(output_dir, job_id)
    last_error = errors[-1] if errors else "Tidak ada detail dari yt-dlp"
    raise YouTubeDownloadError(_friendly_error(last_error, bool(cookie_file)))


def _build_format_selector(max_height: int) -> str:
    """Prefer a smaller rendition when configured, otherwise use best quality."""
    if max_height <= 0:
        return "bv*+ba/b"
    return f"bv*[height<={max_height}]+ba/b[height<={max_height}]"


def _find_downloaded_path(stdout: str, output_dir: Path, job_id: str) -> Path | None:
    for line in reversed(stdout.splitlines()):
        candidate = Path(line.strip())
        if candidate.exists() and candidate.is_file():
            return candidate

    candidates = [
        path for path in output_dir.glob(f"{job_id}.*")
        if path.is_file() and path.suffix not in {".part", ".ytdl", ".json"}
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _should_retry_with_fallback(detail: str) -> bool:
    normalized = detail.lower()
    return any(
        indicator in normalized
        for indicator in (
            "http error 403",
            "http error 429",
            "too many requests",
            "sign in to confirm you're not a bot",
            "missing required visitor data",
            "unable to fetch gvs po token",
            "precondition check failed",
            "http error 400",
            "requested format is not available",
            "only images are available",
            "signature solving failed",
            "challenge solving failed",
        )
    )


def _is_rate_limited_or_bot_block(detail: str) -> bool:
    # yt-dlp/YouTube can render "you're" with either ASCII or typographic
    # apostrophes depending on the response client. Normalize those variants
    # before matching so the user gets actionable guidance instead of raw
    # stderr.
    normalized = detail.lower().replace("’", "'").replace("‘", "'")
    return any(
        indicator in normalized
        for indicator in (
            "http error 429",
            "too many requests",
            "sign in to confirm you're not a bot",
            "missing required visitor data",
            "unable to fetch gvs po token",
        )
    )


def _friendly_error(detail: str, used_cookies: bool = False) -> str:
    normalized = detail.lower()
    if _is_rate_limited_or_bot_block(detail):
        follow_up = (
            "Cookies browser sudah dipakai; buka video di browser pada jaringan yang sama, "
            "selesaikan verifikasi bila diminta, lalu export ulang cookies Netscape dan coba lagi."
            if used_cookies
            else "Tunggu sampai rate-limit reda atau konfigurasi cookies Netscape yang fresh dari browser "
            "pada jaringan yang sama melalui YOUTUBE_COOKIES_PATH."
        )
        return (
            "YouTube sedang memblokir sesi/IP sebagai bot (HTTP 429). ClipGen menghentikan retry otomatis "
            "agar blokir tidak makin parah. "
            f"{follow_up}"
        )
    if "http error 403" in normalized:
        follow_up = (
            "Cookie browser sudah dipakai; buka video tersebut di browser pada jaringan yang sama, "
            "refresh/verifikasi bila diminta, lalu export ulang cookie."
            if used_cookies
            else "Jika Retry masih gagal, gunakan cookies.txt browser yang fresh dari jaringan yang sama "
            "melalui YOUTUBE_COOKIES_PATH."
        )
        return (
            "YouTube menolak stream video (HTTP 403) setelah ClipGen mencoba beberapa playback client. "
            "Ini bukan masalah bandwidth. "
            f"{follow_up}"
        )
    if "precondition check failed" in normalized or "http error 400" in normalized:
        return (
            "YouTube menolak permintaan download saat ini. Coba ulangi beberapa saat lagi, "
            "gunakan URL video publik lain, atau upload file video secara langsung."
        )
    if "js runtime" in normalized or "challenge solving failed" in normalized:
        return "Komponen challenge YouTube belum siap di server. Hubungi administrator untuk memperbarui runtime YouTube."
    return f"YouTube download gagal: {detail[:300]}"


def _usable_cookie_file(cookies_path: Path | str | None) -> Path | None:
    if cookies_path is None:
        return None
    raw_path = str(cookies_path).strip()
    if not raw_path or raw_path == ".":
        return None
    path = Path(raw_path)
    if path.is_file():
        return path
    logger.warning(f"YouTube cookies path tidak ditemukan, melanjutkan tanpa cookies: {path}")
    return None


def _delete_partial_downloads(output_dir: Path, job_id: str) -> None:
    for path in output_dir.glob(f"{job_id}.*"):
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            logger.warning(f"Could not clean partial YouTube download {path}: {error}")
