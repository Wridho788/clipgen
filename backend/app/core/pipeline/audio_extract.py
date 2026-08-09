"""
Stage 1: Ekstrak audio dari video mentah menggunakan ffmpeg.
Fungsi murni: video_path -> audio_path. Tidak menyentuh DB/state.
"""
import subprocess
from pathlib import Path

from loguru import logger


def has_audio_stream(video_path: Path) -> bool:
    """Return True kalau file video punya minimal satu audio stream."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return result.returncode == 0 and "audio" in result.stdout


def extract_audio(video_path: Path, output_dir: Path) -> Path:
    """
    Ekstrak audio track jadi WAV mono 16kHz (format yang disukai Whisper).
    Raises RuntimeError kalau ffmpeg gagal.
    """
    output_path = output_dir / f"{video_path.stem}_audio.wav"

    if not has_audio_stream(video_path):
        raise RuntimeError(
            "Video tidak punya audio track. ClipGen membutuhkan audio/speech "
            "untuk transkripsi dan highlight detection."
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-map", "0:a:0",
        "-ac", "1",          # mono
        "-ar", "16000",      # 16kHz — sample rate standar untuk speech model
        "-vn",                # buang video stream
        str(output_path),
    ]

    logger.info(f"Extracting audio: {video_path.name} -> {output_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"ffmpeg audio extraction failed: {result.stderr}")
        raise RuntimeError(f"Gagal ekstrak audio dari {video_path}: {result.stderr[-500:]}")

    return output_path
