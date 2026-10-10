"""
Canonical clip edit representation (docs/02 §9, docs/03).

One ``ClipEdit`` document is persisted per clip. The editor preview and the
FFmpeg export both read this document; export never uses transient UI values.
All timeline values are integer milliseconds in *source* time.

Caption timing policy when a trim changes (docs/03 §6):
  * cues entirely outside the trimmed range are kept in the document but are
    not rendered, and the editor flags them as "di luar trim";
  * cues that straddle a trim boundary are clamped to the boundary at render
    time; their stored timing is not rewritten.
Keeping the stored cues untouched means widening the trim again restores the
user's corrected captions instead of losing them.
"""
from __future__ import annotations

import re
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.timeline import TimedSegment

EDIT_SCHEMA_VERSION = 1

OutputPreset = Literal["original", "tiktok", "reels", "youtube_shorts", "square", "landscape"]
VisualStyle = Literal["clean", "blur", "crop", "zoom", "split"]

PRESET_DIMENSIONS: dict[str, tuple[int, int]] = {
    "tiktok": (1080, 1920),
    "reels": (1080, 1920),
    "youtube_shorts": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}

MIN_CLIP_MS = 5_000
MAX_CLIP_MS = 120_000
MAX_CUE_WORDS = 7
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class CaptionStyle(BaseModel):
    # Font size is expressed for a 1080 px wide canvas and scaled to the output.
    font_size: int = Field(default=64, ge=24, le=140)
    text_color: str = "#FFFFFF"
    background: Literal["none", "outline", "box"] = "outline"
    background_color: str = "#000000"
    # Vertical centre of the caption block as a fraction of output height.
    position_y: float = Field(default=0.78, ge=0.08, le=0.92)
    max_chars_per_line: int = Field(default=28, ge=12, le=48)
    bold: bool = True

    @field_validator("text_color", "background_color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if not _HEX_COLOR.match(value):
            raise ValueError("Warna harus format hex #RRGGBB")
        return value.upper()


class CaptionCue(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], min_length=1, max_length=40)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(default="", max_length=300)
    # Text as produced by transcription; used to measure caption correction
    # burden (docs/04 §4). ``None`` means the user added the cue manually.
    original_text: Optional[str] = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_timing(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Waktu akhir caption harus setelah waktu mulai")
        self.text = " ".join(self.text.split())
        return self


class CaptionSettings(BaseModel):
    enabled: bool = False
    style: CaptionStyle = Field(default_factory=CaptionStyle)
    cues: list[CaptionCue] = Field(default_factory=list, max_length=600)


class Framing(BaseModel):
    """Crop focus: 0 = left/top edge, 0.5 = centre, 1 = right/bottom edge.

    Mirrors CSS ``object-position`` so the preview and FFmpeg crop agree.
    """

    focus_x: float = Field(default=0.5, ge=0.0, le=1.0)
    focus_y: float = Field(default=0.5, ge=0.0, le=1.0)


class AudioSettings(BaseModel):
    enabled: bool = True
    normalize: bool = False


class ClipEdit(BaseModel):
    schema_version: int = EDIT_SCHEMA_VERSION
    trim_start_ms: int = Field(ge=0)
    trim_end_ms: int = Field(gt=0)
    output_preset: OutputPreset = "original"
    visual_style: VisualStyle = "clean"
    framing: Framing = Field(default_factory=Framing)
    captions: CaptionSettings = Field(default_factory=CaptionSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    watermark_enabled: bool = True

    @model_validator(mode="after")
    def validate_edit(self):
        duration = self.trim_end_ms - self.trim_start_ms
        if duration < MIN_CLIP_MS:
            raise ValueError(f"Durasi klip minimal {MIN_CLIP_MS // 1000} detik")
        if duration > MAX_CLIP_MS:
            raise ValueError(f"Durasi klip maksimal {MAX_CLIP_MS // 1000} detik")
        if self.output_preset == "original":
            # No fixed social canvas exists to blur/split; keep the source frame.
            self.visual_style = "clean"
        elif self.visual_style == "clean":
            self.visual_style = "crop"
        return self

    @property
    def duration_ms(self) -> int:
        return self.trim_end_ms - self.trim_start_ms

    def check_against_source(self, source_duration_ms: int | None) -> None:
        if source_duration_ms and self.trim_end_ms > source_duration_ms:
            raise ValueError("Timestamp akhir melebihi durasi video sumber")

    def rendered_cues(self) -> list[CaptionCue]:
        """Cues visible in the trimmed clip, clamped to the trim boundaries."""
        if not self.captions.enabled:
            return []
        visible = []
        for cue in sorted(self.captions.cues, key=lambda item: item.start_ms):
            if not cue.text.strip():
                continue
            start = max(cue.start_ms, self.trim_start_ms)
            end = min(cue.end_ms, self.trim_end_ms)
            if end - start < 40:
                continue
            visible.append(cue.model_copy(update={"start_ms": start, "end_ms": end}))
        return visible


def output_dimensions(edit: ClipEdit, source_width: int | None, source_height: int | None) -> tuple[int, int]:
    if edit.output_preset in PRESET_DIMENSIONS:
        return PRESET_DIMENSIONS[edit.output_preset]
    width = source_width or 1920
    height = source_height or 1080
    return _even(width), _even(height)


def build_caption_cues(
    segments: list[TimedSegment],
    start_ms: int,
    end_ms: int,
    *,
    max_words: int = MAX_CUE_WORDS,
) -> list[CaptionCue]:
    """
    Turn transcript segments overlapping a clip into short, readable cues.

    Word timestamps are used when available; otherwise time is distributed
    across words proportionally to their length so long words stay on screen
    longer.
    """
    cues: list[CaptionCue] = []
    for segment in segments:
        if segment.end_ms <= start_ms or segment.start_ms >= end_ms:
            continue
        words = _timed_words(segment)
        for index in range(0, len(words), max_words):
            chunk = words[index : index + max_words]
            if not chunk:
                continue
            text = " ".join(word[2] for word in chunk)
            cue_start = chunk[0][0]
            cue_end = chunk[-1][1]
            if cue_end <= start_ms or cue_start >= end_ms or cue_end <= cue_start:
                continue
            cues.append(CaptionCue(start_ms=cue_start, end_ms=cue_end, text=text, original_text=text))
    return cues


def wrap_caption_text(text: str, max_chars: int) -> list[str]:
    """Greedy word wrap shared (by algorithm) with the editor preview."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def default_edit(
    *,
    start_ms: int,
    end_ms: int,
    output_preset: str,
    visual_style: str,
    captions_enabled: bool,
    cues: list[CaptionCue] | None = None,
    watermark_enabled: bool = True,
) -> ClipEdit:
    return ClipEdit(
        trim_start_ms=start_ms,
        trim_end_ms=end_ms,
        output_preset=output_preset,  # type: ignore[arg-type]
        visual_style=visual_style,  # type: ignore[arg-type]
        captions=CaptionSettings(enabled=captions_enabled and bool(cues), cues=cues or []),
        watermark_enabled=watermark_enabled,
    )


def caption_correction_stats(edit: ClipEdit) -> dict[str, int]:
    transcribed = [cue for cue in edit.captions.cues if cue.original_text is not None]
    corrected = [cue for cue in transcribed if cue.text != cue.original_text]
    return {
        "cues": len(edit.captions.cues),
        "transcribed_cues": len(transcribed),
        "corrected_cues": len(corrected),
        "manual_cues": len(edit.captions.cues) - len(transcribed),
    }


def _timed_words(segment: TimedSegment) -> list[tuple[int, int, str]]:
    timestamped = [
        (word.start_ms, word.end_ms, word.text)
        for word in segment.words
        if word.text.strip() and word.end_ms > word.start_ms
    ]
    if timestamped:
        return timestamped
    tokens = segment.text.split()
    if not tokens:
        return []
    total_chars = sum(len(token) + 1 for token in tokens)
    duration = max(1, segment.end_ms - segment.start_ms)
    result = []
    cursor = segment.start_ms
    for index, token in enumerate(tokens):
        share = duration * (len(token) + 1) / total_chars
        token_end = segment.end_ms if index == len(tokens) - 1 else int(round(cursor + share))
        result.append((cursor, max(cursor + 1, token_end), token))
        cursor = token_end
    return result


def _even(value: int) -> int:
    value = max(2, int(value))
    return value if value % 2 == 0 else value - 1
