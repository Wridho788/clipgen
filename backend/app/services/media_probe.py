"""Small ffprobe helpers shared by request validation and background jobs."""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass(frozen=True)
class VideoInfo:
    duration_seconds: float | None
    width: int | None
    height: int | None


def probe_video(file_path: Path) -> VideoInfo | None:
    """Return primary video metadata, or None when ffprobe cannot read a video stream."""
    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=codec_type,width,height",
        "-of", "json",
        str(file_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
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
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        logger.warning(f"Could not probe video {file_path}: {error}")
        return None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
