"""
Post-render export validation (docs/05 §4).

A zero FFmpeg exit code is not proof of a usable file. Every export is probed
and partially decoded before it replaces the previous clip file.
"""
from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import settings
from app.services.media_probe import probe_media

# Container/encoder rounding (frame boundaries, AAC priming) can shift the
# reported duration slightly; anything beyond this is a real trim defect.
DURATION_TOLERANCE_SECONDS = 0.35


@dataclass
class ExportValidation:
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    has_audio: bool = False
    size_bytes: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def validate_export(
    path: Path,
    *,
    expected_width: int,
    expected_height: int,
    expected_duration_seconds: float,
    expects_audio: bool,
    decode_check: bool = True,
) -> ExportValidation:
    result = ExportValidation(ok=False)
    if not path.exists():
        result.checks["exists"] = False
        result.problems.append("File output tidak ada")
        return result
    result.checks["exists"] = True
    result.size_bytes = path.stat().st_size
    result.checks["non_empty"] = result.size_bytes > 0
    if not result.checks["non_empty"]:
        result.problems.append("File output kosong")
        return result

    facts = probe_media(path)
    result.checks["probeable"] = facts is not None
    if facts is None:
        result.problems.append("File output tidak bisa dibaca ffprobe")
        return result

    result.width, result.height = facts.width, facts.height
    result.duration_seconds = facts.duration_seconds
    result.has_audio = facts.has_audio

    result.checks["dimensions"] = (facts.width, facts.height) == (expected_width, expected_height)
    if not result.checks["dimensions"]:
        result.problems.append(
            f"Dimensi {facts.width}x{facts.height}, seharusnya {expected_width}x{expected_height}"
        )

    actual = facts.duration_seconds or 0.0
    result.checks["duration"] = abs(actual - expected_duration_seconds) <= DURATION_TOLERANCE_SECONDS
    if not result.checks["duration"]:
        result.problems.append(
            f"Durasi {actual:.2f}s, seharusnya {expected_duration_seconds:.2f}s "
            f"(toleransi ±{DURATION_TOLERANCE_SECONDS}s)"
        )

    result.checks["audio"] = facts.has_audio == expects_audio
    if not result.checks["audio"]:
        result.problems.append(
            "Audio hilang dari output" if expects_audio else "Output berisi audio padahal audio dimatikan"
        )

    if decode_check:
        result.checks["decodable"] = _decodes(path)
        if not result.checks["decodable"]:
            result.problems.append("Frame awal output gagal di-decode")

    result.ok = all(result.checks.values())
    return result


def _decodes(path: Path, seconds: float = 2.0) -> bool:
    command = [
        "ffmpeg", "-hide_banner", "-v", "error", "-xerror",
        "-i", str(path), "-t", str(seconds), "-f", "null", "-",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=settings.media_probe_timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
