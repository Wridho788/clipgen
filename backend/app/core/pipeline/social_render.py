"""Social-format rendering with optional NVENC acceleration and CPU fallback."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Callable

from loguru import logger

from app.config import settings
from app.services.runtime_capabilities import get_runtime_capabilities


PRESETS: dict[str, tuple[int, int]] = {
    "tiktok": (1080, 1920),
    "reels": (1080, 1920),
    "youtube_shorts": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}


def nvenc_available() -> bool:
    """Return runtime usability, not merely encoder build availability."""
    return get_runtime_capabilities().nvenc_runtime_usable


def select_video_encoder(acceleration: str = "auto") -> str:
    if nvenc_available():
        return "h264_nvenc"
    return "libx264"


def _run_ffmpeg(
    command: list[str],
    on_heartbeat: Callable[[], None] | None = None,
    heartbeat_seconds: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Run FFmpeg while allowing a long CPU render to report liveness."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=max(1.0, heartbeat_seconds))
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                if on_heartbeat is not None:
                    on_heartbeat()
    except BaseException:
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        raise


def run_ffmpeg_with_fallback(
    command: list[str],
    video_encoder: str,
    *,
    on_heartbeat: Callable[[], None] | None = None,
    heartbeat_seconds: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Run a render; CPU fallback remains a last-resort safety net."""
    result = _run_ffmpeg(command, on_heartbeat, heartbeat_seconds)
    if result.returncode == 0 or video_encoder != "h264_nvenc":
        return result

    logger.warning("NVENC render failed; retrying the clip with CPU libx264")
    fallback = list(command)
    encoder_index = fallback.index("-c:v") + 1
    fallback[encoder_index] = "libx264"
    # NVENC's p1–p7/CQ controls are not valid libx264 options. Replace the
    # full encoder tuning set so a rare runtime failure still has a real CPU
    # fallback instead of failing a second time on invalid arguments.
    for flag in ("-preset", "-cq", "-crf"):
        while flag in fallback:
            option_index = fallback.index(flag)
            del fallback[option_index : option_index + 2]
    fallback[encoder_index + 1 : encoder_index + 1] = ["-preset", "veryfast", "-crf", "22"]
    return _run_ffmpeg(fallback, on_heartbeat, heartbeat_seconds)


def render_social_clip(
    clip_path: Path,
    output_dir: Path,
    clip_id: str,
    *,
    output_preset: str,
    visual_style: str,
    acceleration: str = "auto",
    start_time: float | None = None,
    end_time: float | None = None,
    on_heartbeat: Callable[[], None] | None = None,
    heartbeat_seconds: float = 30.0,
    watermark_text: str | None = None,
    watermark_opacity: float | None = None,
    watermark_position: str | None = None,
) -> Path:
    """Render a platform canvas, optionally cutting directly from the source."""
    watermark_text = settings.watermark_text if watermark_text is None and settings.watermark_enabled else watermark_text
    if output_preset == "original" and visual_style == "clean" and not watermark_text:
        return clip_path

    if output_preset == "original" and visual_style == "clean":
        width, height = PRESETS["landscape"]
        filter_graph = _append_watermark(
            "null",
            watermark_text,
            watermark_opacity,
            watermark_position,
            width,
            height,
        ).removeprefix("null,")
        output_path = output_dir / f"{clip_id}_rendered.mp4"
        encoder = select_video_encoder(acceleration)
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        ]
        if start_time is not None:
            command.extend(["-ss", str(start_time)])
        command.extend(["-i", str(clip_path)])
        if end_time is not None:
            command.extend(["-t", str(max(0.1, end_time - (start_time or 0.0)))])
        command.extend(["-vf", filter_graph, "-c:v", encoder])
        if encoder == "libx264":
            command.extend(["-preset", "veryfast", "-crf", "22"])
        else:
            command.extend(["-preset", "p4", "-cq", "23"])
        command.extend(["-c:a", "aac", "-movflags", "+faststart", "-avoid_negative_ts", "make_zero", str(output_path)])
        result = run_ffmpeg_with_fallback(command, encoder, on_heartbeat=on_heartbeat, heartbeat_seconds=heartbeat_seconds)
        if result.returncode != 0:
            raise RuntimeError(f"Gagal render watermark clip {clip_id}: {result.stderr[-500:]}")
        return output_path

    width, height = PRESETS.get(output_preset, PRESETS["tiktok"])
    output_path = output_dir / f"{clip_id}_rendered.mp4"
    encoder = select_video_encoder(acceleration)
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-y"]
    if start_time is not None:
        command.extend(["-ss", str(start_time)])
    command.extend(["-i", str(clip_path)])
    if end_time is not None:
        command.extend(["-t", str(max(0.1, end_time - (start_time or 0.0)))])

    if visual_style == "blur":
        command.extend(["-filter_complex", _blur_background_filter(width, height, watermark_text, watermark_opacity, watermark_position)])
    elif visual_style == "split":
        command.extend(["-filter_complex", _split_filter(width, height, watermark_text, watermark_opacity, watermark_position)])
    else:
        command.extend(["-vf", _single_frame_filter(width, height, visual_style, watermark_text, watermark_opacity, watermark_position)])

    command.extend(["-c:v", encoder])
    if encoder == "libx264":
        command.extend(["-preset", "veryfast", "-crf", "22"])
    else:
        command.extend(["-preset", "p4", "-cq", "23"])
    command.extend(
        [
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-avoid_negative_ts", "make_zero",
            str(output_path),
        ]
    )
    logger.info(
        f"Rendering {clip_id} preset={output_preset} style={visual_style} encoder={encoder}"
    )
    result = run_ffmpeg_with_fallback(
        command,
        encoder,
        on_heartbeat=on_heartbeat,
        heartbeat_seconds=heartbeat_seconds,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Gagal render social clip {clip_id}: {result.stderr[-500:]}")
    return output_path


def _single_frame_filter(
    width: int,
    height: int,
    visual_style: str,
    watermark_text: str | None = None,
    watermark_opacity: float | None = None,
    watermark_position: str | None = None,
) -> str:
    if visual_style == "zoom":
        zoom_width = _even(int(width * 1.12))
        zoom_height = _even(int(height * 1.12))
        result = (
            f"scale={zoom_width}:{zoom_height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    else:
        result = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    return _append_watermark(result, watermark_text, watermark_opacity, watermark_position, width, height)


def _blur_background_filter(
    width: int,
    height: int,
    watermark_text: str | None = None,
    watermark_opacity: float | None = None,
    watermark_position: str | None = None,
) -> str:
    background_width = max(2, width // 2)
    background_height = max(2, height // 2)
    result = (
        "[0:v]split=2[foreground][background];"
        f"[background]scale={background_width}:{background_height}:force_original_aspect_ratio=increase,"
        f"crop={background_width}:{background_height},boxblur=12:6,scale={width}:{height}[background];"
        f"[foreground]scale={width}:{height}:force_original_aspect_ratio=decrease[foreground];"
        "[background][foreground]overlay=(W-w)/2:(H-h)/2"
    )
    return _append_watermark(result, watermark_text, watermark_opacity, watermark_position, width, height)


def _split_filter(
    width: int,
    height: int,
    watermark_text: str | None = None,
    watermark_opacity: float | None = None,
    watermark_position: str | None = None,
) -> str:
    half_height = _even(height // 2)
    result = (
        "[0:v]split=2[top][bottom];"
        f"[top]scale={width}:{half_height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{half_height}[top];"
        f"[bottom]scale={width}:{half_height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{half_height}[bottom];"
        "[top][bottom]vstack=inputs=2"
    )
    return _append_watermark(result, watermark_text, watermark_opacity, watermark_position, width, height)


def _append_watermark(
    filter_graph: str,
    text: str | None,
    opacity: float | None,
    position: str | None,
    width: int,
    height: int,
) -> str:
    if not text:
        return filter_graph
    escaped = _escape_drawtext_text(text)
    alpha = max(0.1, min(1.0, float(opacity if opacity is not None else settings.watermark_opacity)))
    margin = max(18, int(min(width, height) * 0.035))
    fontsize = max(22, int(min(width, height) * 0.035))
    x, y = {
        "bottom_right": (f"w-tw-{margin}", f"h-th-{margin}"),
        "bottom_left": (str(margin), f"h-th-{margin}"),
        "top_right": (f"w-tw-{margin}", str(margin)),
        "top_left": (str(margin), str(margin)),
    }.get(position or settings.watermark_position, (f"w-tw-{margin}", f"h-th-{margin}"))
    drawtext = (
        f"drawtext=text='{escaped}':fontcolor=white@{alpha:.2f}:fontsize={fontsize}:"
        f"x={x}:y={y}:box=1:boxcolor=black@0.25:boxborderw=8"
    )
    return f"{filter_graph},{drawtext}"


def _escape_drawtext_text(value: str) -> str:
    return value.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")


def _even(value: int) -> int:
    return value if value % 2 == 0 else value + 1
