import pytest

from app.core.errors import ErrorCode, PipelineError
from app.core.timeline import (
    ms_to_ffmpeg,
    ms_to_seconds,
    normalize_segments,
    seconds_to_ms,
    segments_to_json,
    validate_clip_range,
)


def test_seconds_and_ms_round_trip_without_float_drift():
    assert seconds_to_ms(36.9335) == 36934
    assert seconds_to_ms(0.1 + 0.2) == 300
    assert ms_to_seconds(36934) == 36.934
    assert ms_to_ffmpeg(73867) == "73.867"
    assert seconds_to_ms(-1) == 0


def test_normalize_sorts_clamps_and_drops_invalid_segments():
    raw = [
        {"start": 5.0, "end": 7.0, "text": "second"},
        {"start": 1.0, "end": 3.0, "text": "first"},
        {"start": 3.0, "end": 2.0, "text": "inverted"},
        {"start": 8.0, "end": 9.0, "text": "   "},
        {"start": 9.5, "end": 12.0, "text": "runs past the end"},
        {"start": 11.0, "end": 13.0, "text": "starts after the end"},
    ]
    segments, report = normalize_segments(raw, duration_ms=10_000)
    assert [segment.text for segment in segments] == ["first", "second", "runs past the end"]
    assert segments[-1].end_ms == 10_000
    assert report.reordered is True
    assert report.dropped_empty == 1
    assert report.dropped_invalid == 2
    assert report.clamped == 1
    assert all(a.end_ms <= b.start_ms for a, b in zip(segments, segments[1:]))


def test_normalize_repairs_overlapping_segments():
    raw = [
        {"start": 0.0, "end": 4.0, "text": "a"},
        {"start": 3.0, "end": 6.0, "text": "b"},
    ]
    segments, report = normalize_segments(raw, duration_ms=None)
    assert segments[0].end_ms == 3_000
    assert segments[1].start_ms == 3_000
    assert report.clamped == 1


def test_normalize_keeps_word_timestamps_inside_segment():
    raw = [{"start": 1.0, "end": 2.0, "text": "hi there", "words": [
        {"start": 0.9, "end": 1.4, "text": "hi"}, {"start": 1.4, "end": 2.2, "text": "there"},
    ]}]
    segments, _ = normalize_segments(raw, duration_ms=5_000)
    assert [(w.start_ms, w.end_ms) for w in segments[0].words] == [(1_000, 1_400), (1_400, 2_000)]
    assert segments_to_json(segments)[0]["words"][0] == {"start": 1.0, "end": 1.4, "text": "hi"}


def test_mostly_invalid_transcript_is_rejected_with_stable_code():
    raw = [{"start": 5, "end": 1, "text": "bad"}] * 5 + [{"start": 0, "end": 1, "text": "ok"}]
    with pytest.raises(PipelineError) as error:
        normalize_segments(raw, duration_ms=10_000)
    assert error.value.code == ErrorCode.TRANSCRIPT_TIMESTAMPS_INVALID


@pytest.mark.parametrize(
    "start,end,duration,message",
    [
        (-1, 10_000, None, "negatif"),
        (5_000, 5_000, None, "setelah"),
        (0, 20_000, 10_000, "melebihi"),
        (0, 3_000, None, "minimal"),
        (0, 130_000, None, "maksimal"),
    ],
)
def test_validate_clip_range_rejects_unusable_ranges(start, end, duration, message):
    with pytest.raises(PipelineError) as error:
        validate_clip_range(start, end, duration)
    assert error.value.code == ErrorCode.CANDIDATE_BOUNDARY_INVALID
    assert message in str(error.value)


def test_validate_clip_range_accepts_valid_range():
    validate_clip_range(1_000, 21_000, 60_000)
