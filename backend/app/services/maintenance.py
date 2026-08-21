"""Low-risk storage maintenance for a local single-user installation."""
import asyncio
import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Clip, ClipFeedback, Job


@dataclass
class CleanupReport:
    files_deleted: int = 0
    bytes_reclaimed: int = 0


@dataclass
class StorageClearReport:
    mode: Literal["recycle", "permanent"]
    files_handled: int = 0
    bytes_moved: int = 0
    bytes_reclaimed: int = 0
    jobs_deleted: int = 0
    clips_deleted: int = 0
    recycle_path: str | None = None


class StorageBusyError(RuntimeError):
    """Raised when a clear would race with a queued or active job."""


def storage_policy() -> dict[str, int | bool]:
    """Expose retention choices so operators know whether assets can disappear."""
    return {
        "temp_cleanup_enabled": settings.temp_cleanup_enabled,
        "temp_file_retention_hours": settings.temp_file_retention_hours,
        "upload_retention_days": settings.upload_retention_days,
        "clip_retention_days": settings.clip_retention_days,
        "permanent_asset_cleanup_enabled": bool(
            settings.upload_retention_days > 0 or settings.clip_retention_days > 0
        ),
    }


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


def clear_workspace_storage(
    db: Session,
    owner_id: str,
    mode: Literal["recycle", "permanent"],
) -> StorageClearReport:
    """Clear a local user's assets and job history after all workers are idle.

    ``recycle`` moves assets to ClipGen's own recycle directory and creates a
    SQLite snapshot before deleting job records.  It is recoverable but does
    not reclaim disk space.  ``permanent`` removes assets, previous recycle
    entries, and job records irreversibly.
    """
    _ensure_no_active_jobs(db)
    jobs = db.query(Job).filter(Job.owner_id == owner_id).all()
    job_ids = [job.id for job in jobs]
    clips = (
        db.query(Clip).filter(Clip.job_id.in_(job_ids)).all()
        if job_ids
        else []
    )
    clip_ids = [clip.id for clip in clips]
    paths = _clearable_asset_files(jobs, clips)
    if mode == "permanent":
        paths.extend(_safe_files(_recycle_root()))
    paths = _deduplicated_files(paths)
    report = StorageClearReport(mode=mode)
    if not paths and not job_ids:
        return report

    if mode == "recycle":
        recycle_path = _new_recycle_path()
        recycle_path.mkdir(parents=True, exist_ok=False)
        _snapshot_database(recycle_path / "app-before-clear.db")
        report.bytes_moved = _total_size(paths)
        _move_to_recycle(paths, recycle_path)
        report.recycle_path = str(recycle_path)
        _write_recycle_manifest(recycle_path, paths, job_ids, clip_ids)
    else:
        report.bytes_reclaimed = _total_size(paths)
        _delete_files_permanently(paths)

    if clip_ids:
        db.query(ClipFeedback).filter(ClipFeedback.clip_id.in_(clip_ids)).delete(
            synchronize_session=False
        )
    if job_ids:
        db.query(Clip).filter(Clip.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
    db.commit()

    report.files_handled = len(paths)
    report.jobs_deleted = len(job_ids)
    report.clips_deleted = len(clip_ids)
    logger.warning(
        "Storage clear complete mode={} files={} jobs={} clips={}",
        mode, report.files_handled, report.jobs_deleted, report.clips_deleted,
    )
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


def _ensure_no_active_jobs(db: Session) -> None:
    active_statuses = (
        "pending",
        "downloading",
        "analyzing_intro",
        "extracting",
        "transcribing",
        "detecting",
        "cutting",
        "cropping",
        "subtitling",
        "generating_metadata",
    )
    active = db.query(Job.id).filter(Job.status.in_(active_statuses)).first()
    if active:
        raise StorageBusyError(
            "Tidak dapat membersihkan storage ketika masih ada job aktif atau menunggu. "
            "Batalkan/selesaikan job tersebut terlebih dahulu."
        )


def _clearable_asset_files(jobs: list[Job], clips: list[Clip]) -> list[Path]:
    paths: list[Path] = list(_safe_files(settings.temp_dir))
    for job in jobs:
        if job.source_path and not job.source_path.startswith(("http://", "https://")):
            source = Path(job.source_path)
            paths.append(source)
            paths.append(source.with_suffix(".info.json"))
    paths.extend(Path(clip.file_path) for clip in clips if clip.file_path)
    return _safe_files(paths)


def _safe_files(paths: Path | list[Path]) -> list[Path]:
    values = list(_iter_files(paths)) if isinstance(paths, Path) and paths.is_dir() else (
        [paths] if isinstance(paths, Path) else paths
    )
    root = settings.storage_dir.resolve()
    result: list[Path] = []
    for path in values:
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            logger.warning(f"Storage clear skipped unsafe path: {path}")
            continue
        if resolved.is_file():
            result.append(resolved)
    return result


def _deduplicated_files(paths: list[Path]) -> list[Path]:
    return list({str(path): path for path in paths if path.is_file()}.values())


def _recycle_root() -> Path:
    return settings.storage_dir / ".recycle-bin"


def _new_recycle_path() -> Path:
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return _recycle_root() / f"clear-{stamp}-{uuid.uuid4().hex[:8]}"


def _snapshot_database(destination: Path) -> None:
    """Create a consistent SQLite backup without moving an open DB file."""
    if not settings.database_url.startswith("sqlite:///"):
        return
    source_path = Path(settings.database_url.removeprefix("sqlite:///"))
    if not source_path.exists():
        return
    source = sqlite3.connect(str(source_path))
    backup = sqlite3.connect(str(destination))
    try:
        source.backup(backup)
    finally:
        backup.close()
        source.close()


def _move_to_recycle(paths: list[Path], recycle_path: Path) -> None:
    root = settings.storage_dir.resolve()
    moved: list[tuple[Path, Path]] = []
    try:
        for source in paths:
            destination = recycle_path / source.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append((source, destination))
    except OSError as error:
        for original, relocated in reversed(moved):
            if relocated.exists() and not original.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(relocated), str(original))
        raise RuntimeError(f"Gagal memindahkan semua file ke Recycle Bin ClipGen: {error}") from error


def _delete_files_permanently(paths: list[Path]) -> None:
    for path in paths:
        path.unlink()


def _total_size(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def _write_recycle_manifest(
    recycle_path: Path,
    paths: list[Path],
    job_ids: list[str],
    clip_ids: list[str],
) -> None:
    root = settings.storage_dir.resolve()
    payload = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "mode": "recycle",
        "jobs_deleted": len(job_ids),
        "clips_deleted": len(clip_ids),
        "files": [str(path.relative_to(root)) for path in paths],
        "database_snapshot": "app-before-clear.db",
    }
    (recycle_path / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
