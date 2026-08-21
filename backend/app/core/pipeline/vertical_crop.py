"""Optional vertical crop stage for manual social-short exports."""
from pathlib import Path

from loguru import logger
from app.core.pipeline.social_render import run_ffmpeg_with_fallback, select_video_encoder


def crop_clip_vertical(
    clip_path: Path,
    output_dir: Path,
    clip_id: str,
    acceleration: str = "auto",
) -> Path:
    """Center-crop a clip to 9:16 while preserving audio."""
    output_path = output_dir / f"{clip_id}_cropped.mp4"
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920"
    )
    encoder = select_video_encoder(acceleration)
    command = [
        "ffmpeg", "-y",
        "-i", str(clip_path),
        "-vf", video_filter,
        "-c:v", encoder,
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        str(output_path),
    ]

    logger.info(f"Cropping clip {clip_id} to vertical 9:16")
    result = run_ffmpeg_with_fallback(command, encoder)
    if result.returncode != 0:
        logger.error(f"ffmpeg vertical crop failed: {result.stderr}")
        raise RuntimeError(f"Gagal crop vertical untuk clip {clip_id}: {result.stderr[-500:]}")

    return output_path
