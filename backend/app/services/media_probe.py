"""Small ffprobe helpers shared by request validation and background jobs."""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from app.config import settings


@dataclass(frozen=True)
class VideoInfo:
    duration_seconds: float | None
    width: int | None
    height: int | None


def probe_video(file_path: Path) -> VideoInfo | None:
    """Return video metadata; a timeout is not evidence of a corrupt video."""
    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=codec_type,width,height",
        "-of", "json",
        str(file_path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=settings.media_probe_timeout_seconds,
        )
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout or "{}")
        stream = next(
            (
                item
                for item in payload.get("streams", [])
                if item.get("codec_type") == "video"
            ),
            None,
        )
        if not stream:
            return None
        duration = payload.get("format", {}).get("duration")
        return VideoInfo(
            duration_seconds=max(0.0, float(duration)) if duration is not None else None,
            width=_optional_int(stream.get("width")),
            height=_optional_int(stream.get("height")),
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        logger.warning(f"Could not probe video {file_path}: {error}")
        return None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class MediaFacts:
    """Everything export validation and render planning need from one probe."""

    duration_seconds: float | None
    width: int | None
    height: int | None
    has_audio: bool
    video_codec: str | None
    frame_rate: float | None
    size_bytes: int


def probe_media(file_path: Path) -> MediaFacts | None:
    """Probe video and audio streams together; ``None`` means not a usable video."""
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate",
        "-of", "json",
        str(file_path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=settings.media_probe_timeout_seconds,
        )
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout or "{}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        logger.warning(f"Could not probe media {file_path}: {error}")
        return None

    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    if not video:
        return None
    duration = payload.get("format", {}).get("duration")
    try:
        duration_seconds = max(0.0, float(duration)) if duration is not None else None
    except (TypeError, ValueError):
        duration_seconds = None
    try:
        size_bytes = file_path.stat().st_size
    except OSError:
        size_bytes = 0
    return MediaFacts(
        duration_seconds=duration_seconds,
        width=_optional_int(video.get("width")),
        height=_optional_int(video.get("height")),
        has_audio=any(item.get("codec_type") == "audio" for item in streams),
        video_codec=video.get("codec_name"),
        frame_rate=_frame_rate(video.get("avg_frame_rate")),
        size_bytes=size_bytes,
    )


def _frame_rate(value: object) -> float | None:
    try:
        numerator, denominator = str(value).split("/")
        rate = float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return round(rate, 3) if rate > 0 else None
