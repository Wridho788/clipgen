"""
Stage 4: Potong video sesuai timestamp highlight menggunakan ffmpeg.
"""
from pathlib import Path
from typing import Callable

from loguru import logger
from app.core.pipeline.social_render import run_ffmpeg_with_fallback, select_video_encoder
from app.core.pipeline.social_render import _append_watermark
from app.config import settings


def cut_clip(
    video_path: Path,
    start: float,
    end: float,
    output_dir: Path,
    clip_id: str,
    acceleration: str = "auto",
    on_heartbeat: Callable[[], None] | None = None,
    heartbeat_seconds: float = 30.0,
    watermark_text: str | None = None,
    watermark_opacity: float | None = None,
    watermark_position: str | None = None,
) -> Path:
    output_path = output_dir / f"{clip_id}_raw.mp4"
    duration = end - start

    encoder = select_video_encoder(acceleration)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        "-ss", str(start),
        "-i", str(video_path),
        "-t", str(duration),
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
    ]
    watermark_text = settings.watermark_text if watermark_text is None and settings.watermark_enabled else watermark_text
    if watermark_text:
        # The original canvas keeps its source dimensions; FFmpeg's drawtext
        # coordinates are relative to the input frame.
        cmd.extend(
            [
                "-vf",
                _append_watermark(
                    "null",
                    watermark_text,
                    watermark_opacity,
                    watermark_position,
                    1080,
                    1920,
                ).removeprefix("null,"),
            ]
        )
    cmd.extend(["-c:v", encoder])
    if encoder == "libx264":
        cmd.extend(["-preset", "veryfast", "-crf", "22"])
    else:
        cmd.extend(["-preset", "p4", "-cq", "23"])
    cmd.append(str(output_path))

    logger.info(f"Cutting clip {clip_id}: {start:.1f}s - {end:.1f}s")
    result = run_ffmpeg_with_fallback(
        cmd,
        encoder,
        on_heartbeat=on_heartbeat,
        heartbeat_seconds=heartbeat_seconds,
    )

    if result.returncode != 0:
        logger.error(f"ffmpeg cut failed: {result.stderr}")
        raise RuntimeError(f"Gagal potong clip {clip_id}: {result.stderr[-500:]}")

    return output_path
