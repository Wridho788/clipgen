"""
Build the FFmpeg export command from a ``ClipEdit`` (docs/02 §9-10).

Pure functions only: given the saved edit and probed source facts, return the
exact argument list and the ASS caption document. The render service executes
them; tests assert on them without running FFmpeg.

Geometry contract shared with the editor preview:
  * ``crop``/``zoom`` scale the source to cover the canvas, then crop with
    ``x = (scaled_w - out_w) * focus_x`` — the same maths as CSS
    ``object-fit: cover; object-position: focus_x focus_y``;
  * caption font size is ``font_size * min(out_w, out_h) / 1080`` and the
    caption block is centred horizontally at ``position_y * out_h``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.edit_model import CaptionCue, CaptionStyle, ClipEdit, output_dimensions, wrap_caption_text
from app.core.timeline import ms_to_ffmpeg

ZOOM_FACTOR = 1.12


@dataclass(frozen=True)
class SourceFacts:
    width: int | None
    height: int | None
    duration_ms: int | None
    has_audio: bool


@dataclass(frozen=True)
class RenderPlan:
    command: list[str]
    width: int
    height: int
    duration_ms: int
    expects_audio: bool
    ass_document: str | None


def caption_scale(width: int, height: int) -> float:
    return min(width, height) / 1080.0


def build_ass_document(edit: ClipEdit, width: int, height: int) -> str | None:
    cues = edit.rendered_cues()
    if not cues:
        return None
    style = edit.captions.style
    scale = caption_scale(width, height)
    font_size = max(8, int(round(style.font_size * scale)))
    if style.background == "box":
        border_style, outline, outline_colour = 3, max(2, int(round(12 * scale))), style.background_color
    elif style.background == "outline":
        border_style, outline, outline_colour = 1, max(1, int(round(5 * scale))), style.background_color
    else:
        border_style, outline, outline_colour = 1, 0, style.background_color
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        # Wrapping is done here (same greedy algorithm as the preview), so
        # libass must not re-wrap lines on its own.
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding",
        (
            f"Style: Caption,DejaVu Sans,{font_size},{_ass_colour(style.text_color)},&H000000FF,"
            f"{_ass_colour(outline_colour)},{_ass_colour(style.background_color, alpha=0x80)},"
            f"{-1 if style.bold else 0},0,0,0,100,100,0,0,{border_style},{outline},0,5,20,20,0,1"
        ),
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    x = width // 2
    y = int(round(style.position_y * height))
    for cue in cues:
        start = cue.start_ms - edit.trim_start_ms
        end = cue.end_ms - edit.trim_start_ms
        text = r"\N".join(_escape_ass_text(line) for line in wrap_caption_text(cue.text, style.max_chars_per_line))
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{{\\an5\\pos({x},{y})}}{text}"
        )
    return "\n".join(lines) + "\n"


def build_video_filter(
    edit: ClipEdit,
    width: int,
    height: int,
    *,
    ass_path: Path | None,
    watermark_filter: str | None,
) -> str:
    """Return a ``-filter_complex`` graph ending in the ``[vout]`` label."""
    fx = f"{edit.framing.focus_x:.4f}"
    fy = f"{edit.framing.focus_y:.4f}"
    style = edit.visual_style
    if edit.output_preset == "original":
        base = "[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2[base]"
    elif style == "blur":
        bw, bh = max(2, width // 2), max(2, height // 2)
        base = (
            "[0:v]split=2[fg][bg];"
            f"[bg]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
            f"boxblur=12:6,scale={width}:{height}[bg];"
            f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
        )
    elif style == "split":
        half = _even(height // 2)
        base = (
            "[0:v]split=2[top][bottom];"
            f"[top]scale={width}:{half}:force_original_aspect_ratio=increase,"
            f"crop={width}:{half}:(iw-ow)*{fx}:(ih-oh)*{fy}[top];"
            f"[bottom]scale={width}:{half}:force_original_aspect_ratio=increase,"
            f"crop={width}:{half}:(iw-ow)*{fx}:(ih-oh)*{fy}[bottom];"
            f"[top][bottom]vstack=inputs=2,scale={width}:{height}[base]"
        )
    else:
        factor = ZOOM_FACTOR if style == "zoom" else 1.0
        sw, sh = _even(int(round(width * factor))), _even(int(round(height * factor)))
        base = (
            f"[0:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:(iw-ow)*{fx}:(ih-oh)*{fy}[base]"
        )
    chain = ["setsar=1"]
    if ass_path is not None:
        chain.append(f"ass=filename='{_escape_filter_path(ass_path)}'")
    if watermark_filter:
        chain.append(watermark_filter)
    chain.append("format=yuv420p")
    return f"{base};[base]{','.join(chain)}[vout]"


def build_render_plan(
    *,
    source_path: Path,
    edit: ClipEdit,
    source: SourceFacts,
    output_path: Path,
    encoder: str,
    ass_path: Path | None,
    watermark_filter: str | None,
) -> RenderPlan:
    width, height = output_dimensions(edit, source.width, source.height)
    if edit.output_preset == "original" and source.width and source.height:
        width, height = _even_floor(source.width), _even_floor(source.height)
    expects_audio = source.has_audio and edit.audio.enabled
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        "-ss", ms_to_ffmpeg(edit.trim_start_ms),
        "-i", str(source_path),
        "-t", ms_to_ffmpeg(edit.duration_ms),
        "-filter_complex", build_video_filter(
            edit, width, height, ass_path=ass_path, watermark_filter=watermark_filter,
        ),
        "-map", "[vout]",
    ]
    if expects_audio:
        command.extend(["-map", "0:a:0"])
        if edit.audio.normalize:
            command.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])
        command.extend(["-c:a", "aac", "-b:a", "160k", "-ar", "48000"])
    else:
        command.append("-an")
    command.extend(["-c:v", encoder])
    if encoder == "libx264":
        command.extend(["-preset", "veryfast", "-crf", "22"])
    else:
        command.extend(["-preset", "p4", "-cq", "23"])
    command.extend(["-movflags", "+faststart", "-avoid_negative_ts", "make_zero", "-f", "mp4", str(output_path)])
    return RenderPlan(
        command=command,
        width=width,
        height=height,
        duration_ms=edit.duration_ms,
        expects_audio=expects_audio,
        ass_document=build_ass_document(edit, width, height),
    )


def _ass_colour(hex_colour: str, alpha: int = 0) -> str:
    value = hex_colour.lstrip("#")
    red, green, blue = value[0:2], value[2:4], value[4:6]
    return f"&H{alpha:02X}{blue}{green}{red}".upper()


def _ass_time(ms: int) -> str:
    centiseconds = max(0, int(round(ms / 10)))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{fraction:02d}"


def _escape_ass_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", r"\{").replace("}", r"\}")


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _even(value: int) -> int:
    value = max(2, int(value))
    return value if value % 2 == 0 else value + 1


def _even_floor(value: int) -> int:
    value = max(2, int(value))
    return value - (value % 2)


__all__ = [
    "CaptionCue",
    "CaptionStyle",
    "RenderPlan",
    "SourceFacts",
    "build_ass_document",
    "build_render_plan",
    "build_video_filter",
    "caption_scale",
]
