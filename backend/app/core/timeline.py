"""
Timeline primitives (docs/02 §5).

Edit data is persisted as integer milliseconds so trims and caption timings do
not drift through float arithmetic. Conversion to seconds or FFmpeg/ASS time
strings happens only at adapter boundaries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.errors import ErrorCode, PipelineError


def seconds_to_ms(value: float | int | None) -> int:
    return max(0, int(round(float(value or 0.0) * 1000)))


def ms_to_seconds(value: int) -> float:
    return round(int(value) / 1000.0, 3)


def ms_to_ffmpeg(value: int) -> str:
    """FFmpeg accepts fractional seconds; three decimals keeps millisecond precision."""
    return f"{max(0, int(value)) / 1000:.3f}"


@dataclass
class TimedWord:
    start_ms: int
    end_ms: int
    text: str


@dataclass
class TimedSegment:
    start_ms: int
    end_ms: int
    text: str
    words: list[TimedWord] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True)
class NormalizationReport:
    input_count: int
    kept_count: int
    dropped_empty: int
    dropped_invalid: int
    clamped: int
    reordered: bool
    repetitions_collapsed: int = 0


def normalize_segments(
    raw_segments: list[dict] | list,
    duration_ms: int | None,
) -> tuple[list[TimedSegment], NormalizationReport]:
    """
    Return transcript segments that are ordered, non-empty, and inside the source.

    Accepts dicts (``start``/``end`` in seconds, as stored in ``transcript_json``)
    or objects with ``start``/``end``/``text`` attributes. Segments that cannot
    be repaired are dropped and counted; if most of a non-trivial transcript is
    invalid the transcript is rejected rather than silently trusted.
    """
    limit = duration_ms if duration_ms and duration_ms > 0 else None
    segments: list[TimedSegment] = []
    dropped_empty = dropped_invalid = clamped = repetitions = 0

    for item in raw_segments or []:
        try:
            start = _field(item, "start")
            end = _field(item, "end")
            text = str(_field(item, "text") or "").strip()
            start_ms = seconds_to_ms(float(start))
            end_ms = seconds_to_ms(float(end))
        except (KeyError, TypeError, ValueError, AttributeError):
            dropped_invalid += 1
            continue
        text, collapsed = collapse_repetitions(text)
        repetitions += collapsed
        if not text:
            dropped_empty += 1
            continue
        if limit is not None:
            if start_ms >= limit:
                dropped_invalid += 1
                continue
            if end_ms > limit:
                end_ms = limit
                clamped += 1
        if end_ms <= start_ms:
            dropped_invalid += 1
            continue
        words = []
        for word in _field(item, "words", default=[]) or []:
            try:
                word_start = seconds_to_ms(float(_field(word, "start")))
                word_end = seconds_to_ms(float(_field(word, "end")))
                word_text = str(_field(word, "text") or "").strip()
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            if word_text and word_end > word_start:
                words.append(
                    TimedWord(max(start_ms, word_start), min(end_ms, word_end), word_text)
                )
        segments.append(TimedSegment(start_ms, end_ms, text, words))

    ordered = sorted(segments, key=lambda segment: (segment.start_ms, segment.end_ms))
    reordered = ordered != segments
    # Overlaps make caption cues flicker on top of each other. Trim the earlier
    # segment back to the next start; drop it when nothing meaningful remains.
    repaired: list[TimedSegment] = []
    for segment in ordered:
        if repaired and segment.start_ms < repaired[-1].end_ms:
            previous = repaired[-1]
            previous.end_ms = segment.start_ms
            clamped += 1
            if previous.end_ms - previous.start_ms < 50:
                repaired.pop()
                dropped_invalid += 1
        repaired.append(segment)

    input_count = len(raw_segments or [])
    report = NormalizationReport(
        input_count=input_count,
        kept_count=len(repaired),
        dropped_empty=dropped_empty,
        dropped_invalid=dropped_invalid,
        clamped=clamped,
        reordered=reordered,
        repetitions_collapsed=repetitions,
    )
    if input_count >= 4 and dropped_invalid > input_count / 2:
        raise PipelineError(
            ErrorCode.TRANSCRIPT_TIMESTAMPS_INVALID,
            f"{dropped_invalid} dari {input_count} segmen transkrip tidak valid",
        )
    return repaired, report


MAX_REPEATS = 2
_TOKEN_CORE = re.compile(r"[\W_]+", re.UNICODE)


def collapse_repetitions(text: str, max_repeats: int = MAX_REPEATS) -> tuple[str, int]:
    """
    Shorten Whisper's decoding loops ("balik balik balik balik …").

    Runs of more than three identical words (case and punctuation ignored)
    are cut to ``max_repeats`` so natural reduplication ("balik balik",
    "ibu ibu") survives. Returns the cleaned text and how many runs were cut.
    """
    tokens = text.split()
    result: list[str] = []
    collapsed = 0
    index = 0
    while index < len(tokens):
        core = _TOKEN_CORE.sub("", tokens[index]).lower()
        end = index + 1
        while core and end < len(tokens) and _TOKEN_CORE.sub("", tokens[end]).lower() == core:
            end += 1
        run = end - index
        if run > 3:
            result.extend(tokens[index:index + max_repeats])
            collapsed += 1
        else:
            result.extend(tokens[index:end])
        index = end
    return " ".join(result), collapsed


def validate_clip_range(
    start_ms: int,
    end_ms: int,
    source_duration_ms: int | None,
    *,
    min_ms: int = 5_000,
    max_ms: int = 120_000,
) -> None:
    """Raise ``PipelineError(CANDIDATE_BOUNDARY_INVALID)`` for an unusable range."""
    if start_ms < 0:
        raise PipelineError(ErrorCode.CANDIDATE_BOUNDARY_INVALID, "Waktu mulai negatif")
    if end_ms <= start_ms:
        raise PipelineError(ErrorCode.CANDIDATE_BOUNDARY_INVALID, "Waktu akhir harus setelah waktu mulai")
    if source_duration_ms and end_ms > source_duration_ms:
        raise PipelineError(
            ErrorCode.CANDIDATE_BOUNDARY_INVALID,
            "Timestamp akhir melebihi durasi video sumber",
        )
    duration = end_ms - start_ms
    if duration < min_ms:
        raise PipelineError(
            ErrorCode.CANDIDATE_BOUNDARY_INVALID, f"Durasi klip minimal {min_ms // 1000} detik"
        )
    if duration > max_ms:
        raise PipelineError(
            ErrorCode.CANDIDATE_BOUNDARY_INVALID, f"Durasi klip maksimal {max_ms // 1000} detik"
        )


def segments_to_json(segments: list[TimedSegment]) -> list[dict]:
    """Serialize back to the seconds-based ``transcript_json`` shape."""
    return [
        {
            "start": ms_to_seconds(segment.start_ms),
            "end": ms_to_seconds(segment.end_ms),
            "text": segment.text,
            "words": [
                {"start": ms_to_seconds(word.start_ms), "end": ms_to_seconds(word.end_ms), "text": word.text}
                for word in segment.words
            ],
        }
        for segment in segments
    ]


def _field(item, name: str, default=KeyError):
    if isinstance(item, dict):
        if name in item:
            return item[name]
    elif hasattr(item, name):
        return getattr(item, name)
    if default is KeyError:
        raise KeyError(name)
    return default
