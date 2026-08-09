"""Optional vertical crop stage for manual social-short exports."""
import subprocess
from pathlib import Path

from loguru import logger


def crop_clip_vertical(clip_path: Path, output_dir: Path, clip_id: str) -> Path:
    """Center-crop a clip to 9:16 while preserving audio."""
    output_path = output_dir / f"{clip_id}_cropped.mp4"
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920"
    )
    command = [
        "ffmpeg", "-y",
        "-i", str(clip_path),
        "-vf", video_filter,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        str(output_path),
    ]

    logger.info(f"Cropping clip {clip_id} to vertical 9:16")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"ffmpeg vertical crop failed: {result.stderr}")
        raise RuntimeError(f"Gagal crop vertical untuk clip {clip_id}: {result.stderr[-500:]}")

    return output_path
