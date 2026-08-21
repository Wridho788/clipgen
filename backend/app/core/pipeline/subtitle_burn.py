"""Burn standard or word-highlighted karaoke captions plus an optional hook."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Callable

from loguru import logger

from app.core.pipeline.social_render import run_ffmpeg_with_fallback, select_video_encoder
from app.core.pipeline.transcribe import Segment, Word


def burn_subtitles(
    clip_path: Path,
    segments: list[Segment],
    clip_id: str,
    output_dir: Path,
    clip_start_time: float = 0.0,
    margin_seconds: float = 1.0,
    *,
    include_subtitles: bool = True,
    subtitle_style: str = "standard",
    hook_text: str | None = None,
    acceleration: str = "auto",
    on_heartbeat: Callable[[], None] | None = None,
    heartbeat_seconds: float = 30.0,
) -> Path:
    """Render captions and/or a branded opening hook onto a finished clip."""
    output_path = output_dir / f"{clip_id}_final.mp4"
    clip_duration = _probe_duration(clip_path)
    adjusted_segments = _adjust_segments(
        segments,
        clip_start_time,
        clip_duration,
        margin_seconds,
    ) if include_subtitles else []

    if not adjusted_segments and not hook_text:
        logger.warning(f"Clip {clip_id}: tidak ada subtitle atau hook untuk di-render")
        return clip_path

    use_ass = subtitle_style == "karaoke" or bool(hook_text)
    overlay_path = output_dir / (f"{clip_id}_subs.ass" if use_ass else f"{clip_id}_subs.srt")
    if use_ass:
        _write_ass(overlay_path, adjusted_segments, subtitle_style, hook_text, clip_duration)
        video_filter = f"ass='{_escape_filter_path(overlay_path)}'"
    else:
        _write_srt(overlay_path, adjusted_segments)
        video_filter = (
            f"subtitles='{_escape_filter_path(overlay_path)}':"
            "force_style='FontSize=24,PrimaryColour=&H00FFFFFF&'"
        )

    encoder = select_video_encoder(acceleration)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        "-i", str(clip_path),
        "-vf", video_filter,
        "-c:v", encoder,
    ]
    if encoder == "libx264":
        command.extend(["-preset", "veryfast", "-crf", "22"])
    else:
        command.extend(["-preset", "p4", "-cq", "23"])
    command.extend(["-c:a", "copy", "-movflags", "+faststart", str(output_path)])

    logger.info(
        f"Burning {subtitle_style} captions for {clip_id}; hook={bool(hook_text)} encoder={encoder}"
    )
    result = run_ffmpeg_with_fallback(
        command,
        encoder,
        on_heartbeat=on_heartbeat,
        heartbeat_seconds=heartbeat_seconds,
    )
    overlay_path.unlink(missing_ok=True)
    if result.returncode != 0:
        logger.error(f"ffmpeg subtitle render failed: {result.stderr}")
        raise RuntimeError(f"Gagal render subtitle untuk clip {clip_id}: {result.stderr[-500:]}")
    return output_path


def _probe_duration(clip_path: Path) -> float:
    command = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(clip_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    try:
        return float(result.stdout.strip()) if result.stdout.strip() else 60.0
    except ValueError:
        logger.warning(f"Gagal parse durasi {clip_path.name}; menggunakan fallback 60s")
        return 60.0


def _adjust_segments(
    segments: list[Segment],
    clip_start_time: float,
    clip_duration: float,
    margin_seconds: float,
) -> list[Segment]:
    clip_end = clip_start_time + clip_duration
    start = max(0.0, clip_start_time - margin_seconds)
    end = clip_end + margin_seconds
    adjusted: list[Segment] = []
    for segment in segments:
        if segment.start >= end or segment.end <= start:
            continue
        adjusted_start = max(0.0, segment.start - clip_start_time)
        adjusted_end = min(clip_duration, segment.end - clip_start_time)
        if adjusted_start >= adjusted_end:
            continue
        words = [
            Word(
                start=max(0.0, word.start - clip_start_time),
                end=min(clip_duration, word.end - clip_start_time),
                text=word.text,
            )
            for word in segment.words
            if word.end > clip_start_time and word.start < clip_end
        ]
        adjusted.append(Segment(adjusted_start, adjusted_end, segment.text, words))
    return adjusted


def _write_srt(path: Path, segments: list[Segment]) -> None:
    with open(path, "w", encoding="utf-8") as output:
        for index, segment in enumerate(segments, 1):
            output.write(
                f"{index}\n{_seconds_to_srt_time(segment.start)} --> "
                f"{_seconds_to_srt_time(segment.end)}\n{segment.text}\n\n"
            )


def _write_ass(
    path: Path,
    segments: list[Segment],
    subtitle_style: str,
    hook_text: str | None,
    clip_duration: float,
) -> None:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Caption,Arial,54,&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,70,70,170,1",
        "Style: Hook,Arial,64,&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,5,1,8,70,70,145,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    if hook_text:
        lines.append(
            f"Dialogue: 0,0:00:00.00,{_ass_time(min(3.5, clip_duration))},Hook,,0,0,0,,"
            f"{{\\an8\\blur2}}{_escape_ass_text(hook_text)}"
        )

    for segment in segments:
        if subtitle_style == "karaoke":
            lines.extend(_karaoke_events(segment))
        else:
            lines.append(
                f"Dialogue: 0,{_ass_time(segment.start)},{_ass_time(segment.end)},Caption,,0,0,0,,"
                f"{{\\an2\\blur1}}{_escape_ass_text(segment.text)}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _karaoke_events(segment: Segment) -> list[str]:
    words = _words_for_segment(segment)
    events = []
    for active_index, active_word in enumerate(words):
        if active_word.end <= active_word.start:
            continue
        styled_words = []
        for index, word in enumerate(words):
            style = "{\\c&H0000FFFF&\\bord7\\blur3}" if index == active_index else "{\\c&H00FFFFFF&\\bord4}"
            styled_words.append(f"{style}{_escape_ass_text(word.text)}")
        events.append(
            f"Dialogue: 0,{_ass_time(active_word.start)},{_ass_time(active_word.end)},Caption,,0,0,0,,"
            f"{{\\an2}}{' '.join(styled_words)}"
        )
    return events


def _words_for_segment(segment: Segment) -> list[Word]:
    timestamped = [word for word in segment.words if word.text.strip() and word.end > word.start]
    if timestamped:
        return timestamped

    tokens = re.findall(r"\S+", segment.text)
    if not tokens:
        return []
    duration = max(0.01, segment.end - segment.start)
    step = duration / len(tokens)
    return [
        Word(segment.start + index * step, segment.start + (index + 1) * step, token)
        for index, token in enumerate(tokens)
    ]


def _seconds_to_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, fractions = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{fractions:02d}"


def _escape_ass_text(value: str) -> str:
    return value.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
