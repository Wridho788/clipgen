"""Low-risk storage maintenance for a local single-user installation."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from app.config import settings


@dataclass
class CleanupReport:
    files_deleted: int = 0
    bytes_reclaimed: int = 0


def cleanup_temporary_files() -> CleanupReport:
    """Delete only old temp files and known intermediate render artifacts."""
    if not settings.temp_cleanup_enabled:
        return CleanupReport()

    cutoff = datetime.utcnow() - timedelta(hours=settings.temp_file_retention_hours)
    candidates = list(_iter_files(settings.temp_dir))
    for suffix in ("*_raw.mp4", "*_cropped.mp4", "*_subs.srt"):
        candidates.extend(path for path in settings.clips_dir.glob(suffix) if path.is_file())

    report = CleanupReport()
    for path in candidates:
        try:
            modified_at = datetime.utcfromtimestamp(path.stat().st_mtime)
            if modified_at >= cutoff:
                continue
            size = path.stat().st_size
            path.unlink()
            report.files_deleted += 1
            report.bytes_reclaimed += size
        except FileNotFoundError:
            continue
        except OSError as error:
            logger.warning(f"Cleanup skipped {path}: {error}")
    return report


async def maintenance_loop() -> None:
    """Run cleanup at a modest interval without blocking FastAPI's event loop."""
    interval_seconds = max(1, settings.temp_cleanup_interval_hours) * 3600
    while True:
        report = await asyncio.to_thread(cleanup_temporary_files)
        if report.files_deleted:
            logger.info(
                "Temporary cleanup removed "
                f"{report.files_deleted} files ({report.bytes_reclaimed} bytes)"
            )
        await asyncio.sleep(interval_seconds)


def _iter_files(directory: Path):
    if not directory.exists():
        return []
    return (path for path in directory.rglob("*") if path.is_file())
