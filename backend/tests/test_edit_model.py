import pytest
from pydantic import ValidationError

from app.core.edit_model import (
    CaptionCue,
    CaptionSettings,
    CaptionStyle,
    ClipEdit,
    build_caption_cues,
    caption_correction_stats,
    default_edit,
    output_dimensions,
    wrap_caption_text,
)
from app.core.timeline import TimedSegment, TimedWord


def _edit(**overrides) -> ClipEdit:
    data = {"trim_start_ms": 10_000, "trim_end_ms": 30_000}
    data.update(overrides)
    return ClipEdit(**data)


def test_edit_enforces_duration_limits():
    with pytest.raises(ValidationError, match="minimal"):
        _edit(trim_end_ms=12_000)
    with pytest.raises(ValidationError, match="maksimal"):
        _edit(trim_end_ms=200_000)


def test_edit_normalizes_style_for_preset():
    assert _edit(output_preset="original", visual_style="blur").visual_style == "clean"
    assert _edit(output_preset="tiktok", visual_style="clean").visual_style == "crop"


def test_edit_rejects_bad_colours_and_cue_timing():
    with pytest.raises(ValidationError):
        CaptionStyle(text_color="white")
    with pytest.raises(ValidationError):
        CaptionCue(start_ms=2_000, end_ms=1_000, text="x")


def test_check_against_source_duration():
    with pytest.raises(ValueError, match="melebihi"):
        _edit().check_against_source(25_000)
    _edit().check_against_source(60_000)


def test_rendered_cues_follow_documented_trim_policy():
    cues = [
        CaptionCue(id="before", start_ms=1_000, end_ms=2_000, text="outside before"),
        CaptionCue(id="straddle", start_ms=9_000, end_ms=11_000, text="straddles start"),
        CaptionCue(id="inside", start_ms=15_000, end_ms=16_000, text="inside"),
        CaptionCue(id="empty", start_ms=17_000, end_ms=18_000, text="   "),
        CaptionCue(id="after", start_ms=31_000, end_ms=32_000, text="outside after"),
    ]
    edit = _edit(captions=CaptionSettings(enabled=True, cues=cues))
    rendered = edit.rendered_cues()
    assert [cue.id for cue in rendered] == ["straddle", "inside"]
    assert rendered[0].start_ms == 10_000  # clamped at render time
    # Stored cues are untouched so widening the trim restores them.
    assert [cue.id for cue in edit.captions.cues] == ["before", "straddle", "inside", "empty", "after"]
    assert edit.captions.cues[1].start_ms == 9_000


def test_disabled_captions_render_nothing():
    edit = _edit(captions=CaptionSettings(enabled=False, cues=[CaptionCue(start_ms=11_000, end_ms=12_000, text="x")]))
    assert edit.rendered_cues() == []


def test_wrap_caption_text_is_greedy_and_never_drops_words():
    assert wrap_caption_text("one two three four five", 9) == ["one two", "three", "four five"]
    assert wrap_caption_text("supercalifragilistic word", 5) == ["supercalifragilistic", "word"]
    assert wrap_caption_text("", 10) == []


def test_build_caption_cues_uses_word_timestamps_when_available():
    segment = TimedSegment(0, 3_000, "a b c", [TimedWord(0, 500, "a"), TimedWord(600, 1_200, "b"), TimedWord(1_300, 3_000, "c")])
    cues = build_caption_cues([segment], 0, 10_000, max_words=2)
    assert [(cue.start_ms, cue.end_ms, cue.text) for cue in cues] == [(0, 1_200, "a b"), (1_300, 3_000, "c")]
    assert cues[0].original_text == "a b"


def test_build_caption_cues_distributes_time_proportionally_without_words():
    segment = TimedSegment(1_000, 5_000, "short muchlongerword")
    cues = build_caption_cues([segment], 0, 10_000, max_words=1)
    assert cues[0].start_ms == 1_000 and cues[-1].end_ms == 5_000
    assert (cues[1].end_ms - cues[1].start_ms) > (cues[0].end_ms - cues[0].start_ms)
    assert all(a.end_ms <= b.start_ms for a, b in zip(cues, cues[1:]))


def test_build_caption_cues_skips_segments_outside_range():
    segments = [TimedSegment(0, 1_000, "before"), TimedSegment(20_000, 21_000, "after")]
    assert build_caption_cues(segments, 5_000, 15_000) == []


def test_default_edit_disables_captions_without_cues():
    edit = default_edit(start_ms=0, end_ms=20_000, output_preset="tiktok", visual_style="blur", captions_enabled=True, cues=[])
    assert edit.captions.enabled is False
    assert edit.visual_style == "blur"


def test_caption_correction_stats_counts_user_corrections():
    cues = [
        CaptionCue(start_ms=10_000, end_ms=11_000, text="fixed", original_text="fxed"),
        CaptionCue(start_ms=11_000, end_ms=12_000, text="same", original_text="same"),
        CaptionCue(start_ms=12_000, end_ms=13_000, text="manual"),
    ]
    stats = caption_correction_stats(_edit(captions=CaptionSettings(enabled=True, cues=cues)))
    assert stats == {"cues": 3, "transcribed_cues": 2, "corrected_cues": 1, "manual_cues": 1}


def test_output_dimensions():
    assert output_dimensions(_edit(output_preset="tiktok", visual_style="crop"), 640, 360) == (1080, 1920)
    assert output_dimensions(_edit(output_preset="original"), 641, 361) == (640, 360)
