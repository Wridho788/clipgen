"""
Stage 6: Burn subtitles ke video.

Proses:
1. Filter segments yang overlap dengan clip duration
2. Adjust timestamps (relative to clip start = 0)
3. Generate SRT format
4. Burn ke video via ffmpeg dengan ASS/SRT subtitle filter
"""
from pathlib import Path
import subprocess

from loguru import logger

from app.core.pipeline.transcribe import Segment


def burn_subtitles(
    clip_path: Path,
    segments: list[Segment],
    clip_id: str,
    output_dir: Path,
    clip_start_time: float = 0.0,
    margin_seconds: float = 1.0,
) -> Path:
    """
    Burn subtitle ke clip.
    
    Args:
        clip_path: path video yang sudah di-crop
        segments: list Segment dari transkripsi full video
        clip_id: ID clip (untuk naming output)
        output_dir: direktori output
        clip_start_time: timestamp awal clip di video asli
        margin_seconds: margin sebelum/sesudah clip untuk ambil subtitle (supaya tidak terpotong punchline)
    
    Return: path file final dengan subtitle ter-burn
    """
    output_path = output_dir / f"{clip_id}_final.mp4"
    
    # Dapatkan clip duration dari ffmpeg (karena file sudah di-crop)
    import subprocess
    cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(clip_path)]
    result = subprocess.run(cmd_dur, capture_output=True, text=True)
    try:
        clip_duration = float(result.stdout.strip()) if result.stdout.strip() else 60.0
    except ValueError:
        logger.warning(f"Clip {clip_id}: gagal parse durasi ffprobe, fallback 60s")
        clip_duration = 60.0
    
    # Filter segments yang overlap dengan window clip di timeline video asli.
    clip_end_time = clip_start_time + clip_duration
    subtitle_start = max(0.0, clip_start_time - margin_seconds)
    subtitle_end = clip_end_time + margin_seconds
    
    relevant_segments = [
        s for s in segments
        if s.start < subtitle_end and s.end > subtitle_start
    ]
    
    if not relevant_segments:
        logger.warning(f"Clip {clip_id}: tidak ada segment subtitle, burn skip")
        return clip_path  # return original tanpa subtitle
    
    # Adjust timestamps relative to clip start
    adjusted_segments = []
    for seg in relevant_segments:
        adj_start = max(0, seg.start - clip_start_time)
        adj_end = min(clip_duration, seg.end - clip_start_time)
        if adj_start < adj_end:
            adjusted_segments.append(
                Segment(start=adj_start, end=adj_end, text=seg.text)
            )

    if not adjusted_segments:
        logger.warning(f"Clip {clip_id}: segment subtitle di luar durasi clip, burn skip")
        return clip_path
    
    # Generate SRT format
    srt_path = output_dir / f"{clip_id}_subs.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(adjusted_segments, 1):
            start_str = _seconds_to_srt_time(seg.start)
            end_str = _seconds_to_srt_time(seg.end)
            f.write(f"{idx}\n{start_str} --> {end_str}\n{seg.text}\n\n")
    
    logger.info(f"Generated subtitle SRT: {srt_path} dengan {len(adjusted_segments)} segments")
    
    # Burn subtitle ke video via ffmpeg
    # Gunakan subtitles filter dengan font kecil, positioning bawah, warna putih
    subtitle_filter = (
        f"subtitles='{_escape_filter_path(srt_path)}':"
        "force_style='FontSize=24,PrimaryColour=&H00FFFFFF&'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(clip_path),
        "-vf", subtitle_filter,
        "-c:a", "copy",
        str(output_path),
    ]
    
    logger.info(f"Burning subtitle ke clip {clip_id}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"ffmpeg subtitle burn failed: {result.stderr}")
        raise RuntimeError(f"Gagal burn subtitle untuk clip {clip_id}: {result.stderr[-500:]}")
    
    # Cleanup SRT file
    srt_path.unlink()
    return output_path


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT time format HH:MM:SS,mmm"""
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _escape_filter_path(path: Path) -> str:
    """Escape path for ffmpeg filter syntax, including Windows drive colons."""
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
