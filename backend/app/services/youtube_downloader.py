"""yt-dlp integration with retries and user-safe YouTube error messages."""
import subprocess
from pathlib import Path

from loguru import logger


class YouTubeDownloadError(RuntimeError):
    """Download failed after yt-dlp's normal and fallback attempts."""


def download_youtube_video(
    url: str,
    output_dir: Path,
    job_id: str,
    timeout_seconds: int,
) -> Path:
    output_template = output_dir / f"{job_id}.%(ext)s"
    attempts = [None, "youtube:player_client=web_safari"]
    errors = []

    for extractor_args in attempts:
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--no-progress",
            "--retries", "3",
            "--fragment-retries", "3",
            "--merge-output-format", "mp4",
            "--write-info-json",
            "--print", "after_move:filepath",
            "--js-runtimes", "deno",
            "-f", "bv*+ba/b",
            "-o", str(output_template),
        ]
        if extractor_args:
            cmd.extend(["--extractor-args", extractor_args])
        cmd.append(url)

        logger.info(f"YouTube download attempt for job {job_id}, fallback={bool(extractor_args)}")
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
                return downloaded_path
            errors.append("yt-dlp selesai tetapi file output tidak ditemukan")
            continue

        detail = (result.stderr or result.stdout).strip()
        errors.append(detail[-600:])
        logger.warning(f"yt-dlp attempt failed for job {job_id}: {detail[-600:]}")
        if not _should_retry_with_fallback(detail):
            break

    _delete_partial_downloads(output_dir, job_id)
    last_error = errors[-1] if errors else "Tidak ada detail dari yt-dlp"
    raise YouTubeDownloadError(_friendly_error(last_error))


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
            "precondition check failed",
            "http error 400",
            "requested format is not available",
            "only images are available",
            "signature solving failed",
            "challenge solving failed",
        )
    )


def _friendly_error(detail: str) -> str:
    normalized = detail.lower()
    if "precondition check failed" in normalized or "http error 400" in normalized:
        return (
            "YouTube menolak permintaan download saat ini. Coba ulangi beberapa saat lagi, "
            "gunakan URL video publik lain, atau upload file video secara langsung."
        )
    if "js runtime" in normalized or "challenge solving failed" in normalized:
        return "Komponen challenge YouTube belum siap di server. Hubungi administrator untuk memperbarui runtime YouTube."
    return f"YouTube download gagal: {detail[:300]}"


def _delete_partial_downloads(output_dir: Path, job_id: str) -> None:
    for path in output_dir.glob(f"{job_id}.*"):
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            logger.warning(f"Could not clean partial YouTube download {path}: {error}")
