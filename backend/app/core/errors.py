"""
Stable failure taxonomy (docs/04 §7).

Every user-visible failure carries a stable ``ErrorCode`` plus a plain-language
message. Technical detail is sanitized before it is stored or logged so storage
paths and secrets do not leak into the UI.
"""
from __future__ import annotations

import re
import subprocess
from enum import Enum


class ErrorCode(str, Enum):
    SOURCE_UNSUPPORTED = "SOURCE_UNSUPPORTED"
    SOURCE_CORRUPT = "SOURCE_CORRUPT"
    SOURCE_MISSING = "SOURCE_MISSING"
    SOURCE_TOO_LARGE = "SOURCE_TOO_LARGE"
    SOURCE_PROBE_TIMEOUT = "SOURCE_PROBE_TIMEOUT"
    AUDIO_MISSING = "AUDIO_MISSING"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    TRANSCRIPTION_TIMEOUT = "TRANSCRIPTION_TIMEOUT"
    TRANSCRIPT_TIMESTAMPS_INVALID = "TRANSCRIPT_TIMESTAMPS_INVALID"
    CANDIDATE_EMPTY = "CANDIDATE_EMPTY"
    CANDIDATE_BOUNDARY_INVALID = "CANDIDATE_BOUNDARY_INVALID"
    EDIT_INVALID = "EDIT_INVALID"
    EDIT_CONFLICT = "EDIT_CONFLICT"
    PREVIEW_FAILED = "PREVIEW_FAILED"
    EXPORT_FAILED = "EXPORT_FAILED"
    EXPORT_VALIDATION_FAILED = "EXPORT_VALIDATION_FAILED"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    INTERRUPTED = "INTERRUPTED"
    UNKNOWN = "UNKNOWN"


USER_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.SOURCE_UNSUPPORTED: "Format file tidak didukung. Gunakan video MP4, MOV, MKV, atau WebM.",
    ErrorCode.SOURCE_CORRUPT: "File bukan video valid atau rusak.",
    ErrorCode.SOURCE_MISSING: "File sumber tidak ditemukan. Upload ulang video untuk memprosesnya.",
    ErrorCode.SOURCE_TOO_LARGE: "File terlalu besar untuk batas upload lokal.",
    ErrorCode.SOURCE_PROBE_TIMEOUT: "Pemeriksaan video/audio melewati batas waktu.",
    ErrorCode.AUDIO_MISSING: "Video tidak punya audio track. Gunakan video dengan suara/speech.",
    ErrorCode.DOWNLOAD_FAILED: "Video sumber gagal diunduh.",
    ErrorCode.TRANSCRIPTION_FAILED: "Transkripsi gagal. Jalankan ulang job untuk mencoba lagi.",
    ErrorCode.TRANSCRIPTION_TIMEOUT: "Transkripsi melewati batas waktu dan dihentikan.",
    ErrorCode.TRANSCRIPT_TIMESTAMPS_INVALID: "Timestamp transkrip tidak valid untuk video ini.",
    ErrorCode.CANDIDATE_EMPTY: "Tidak ada kandidat klip yang bisa dibuat dari video ini.",
    ErrorCode.CANDIDATE_BOUNDARY_INVALID: "Rentang klip tidak valid untuk durasi video sumber.",
    ErrorCode.EDIT_INVALID: "Pengaturan edit tidak valid.",
    ErrorCode.EDIT_CONFLICT: "Ada versi edit yang lebih baru. Muat ulang klip sebelum menyimpan.",
    ErrorCode.PREVIEW_FAILED: "Preview gagal dimuat.",
    ErrorCode.EXPORT_FAILED: "Render klip gagal. Edit tetap tersimpan dan render bisa diulang.",
    ErrorCode.EXPORT_VALIDATION_FAILED: "File hasil render tidak lolos validasi. Edit tetap tersimpan dan render bisa diulang.",
    ErrorCode.RESOURCE_LIMIT_EXCEEDED: "Proses melebihi batas resource lokal.",
    ErrorCode.INTERRUPTED: "Proses terhenti karena backend restart.",
    ErrorCode.UNKNOWN: "Terjadi kesalahan yang tidak terduga.",
}


class PipelineError(RuntimeError):
    """A failure with a stable code; ``detail`` is sanitized technical context."""

    def __init__(self, code: ErrorCode, detail: str | None = None, message: str | None = None):
        self.code = code
        self.user_message = message or USER_MESSAGES[code]
        self.detail = sanitize_detail(detail) if detail else None
        super().__init__(self.user_message if not self.detail else f"{self.user_message} ({self.detail})")


_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:)?(?:[\\/][\w.@~+-]+){2,}")
_SECRET_PATTERN = re.compile(r"(?i)(token|secret|password|cookie|authorization)[=:]\s*\S+")


def sanitize_detail(value: str, limit: int = 400) -> str:
    """Strip filesystem paths and credential-looking pairs, then truncate."""
    cleaned = _SECRET_PATTERN.sub(r"\1=[redacted]", str(value))
    cleaned = _PATH_PATTERN.sub(lambda match: "<path>/" + re.split(r"[\\/]", match.group(0))[-1], cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned[-limit:] if len(cleaned) > limit else cleaned


def classify_exception(error: BaseException) -> ErrorCode:
    """Map an arbitrary exception to the closest stable code."""
    if isinstance(error, PipelineError):
        return error.code
    if isinstance(error, FileNotFoundError):
        return ErrorCode.SOURCE_MISSING
    if isinstance(error, subprocess.TimeoutExpired):
        return ErrorCode.SOURCE_PROBE_TIMEOUT
    if isinstance(error, MemoryError):
        return ErrorCode.RESOURCE_LIMIT_EXCEEDED
    name = type(error).__name__
    text = str(error).lower()
    if name == "TranscriptionTimeoutError":
        return ErrorCode.TRANSCRIPTION_TIMEOUT
    if "transkripsi" in text or "transcri" in text:
        return ErrorCode.TRANSCRIPTION_FAILED
    if "audio track" in text:
        return ErrorCode.AUDIO_MISSING
    if "corrupt" in text or "tidak valid" in text:
        return ErrorCode.SOURCE_CORRUPT
    if "youtube" in text or "yt-dlp" in text or "download" in text or "unduh" in text:
        return ErrorCode.DOWNLOAD_FAILED
    if "no space left" in text or "cannot allocate memory" in text:
        return ErrorCode.RESOURCE_LIMIT_EXCEEDED
    return ErrorCode.UNKNOWN


def describe_failure(error: BaseException) -> tuple[ErrorCode, str]:
    """Return ``(code, message)`` suitable for persistence and display."""
    code = classify_exception(error)
    if isinstance(error, PipelineError):
        return code, str(error)[:500]
    detail = sanitize_detail(str(error))
    if code == ErrorCode.UNKNOWN:
        return code, (detail or USER_MESSAGES[code])[:500]
    base = USER_MESSAGES[code]
    return code, (f"{base} ({detail})" if detail and detail not in base else base)[:500]
