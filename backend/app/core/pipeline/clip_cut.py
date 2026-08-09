"""
Stage 4: Potong video sesuai timestamp highlight menggunakan ffmpeg.
"""
import subprocess
from pathlib import Path

from loguru import logger


def cut_clip(video_path: Path, start: float, end: float, output_dir: Path, clip_id: str) -> Path:
    output_path = output_dir / f"{clip_id}_raw.mp4"
    duration = end - start

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(video_path),
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        str(output_path),
    ]

    logger.info(f"Cutting clip {clip_id}: {start:.1f}s - {end:.1f}s")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"ffmpeg cut failed: {result.stderr}")
        raise RuntimeError(f"Gagal potong clip {clip_id}: {result.stderr[-500:]}")

    return output_path
