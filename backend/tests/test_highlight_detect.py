import numpy as np

from app.core.pipeline.highlight_detect import detect_highlights
from app.core.pipeline.transcribe import Segment


def test_detect_highlights_returns_empty_without_transcript_segments():
    assert detect_highlights([], audio_path="missing.wav", duration=0) == []


def test_detect_highlights_skips_intro_and_returns_distinct_candidates(monkeypatch):
    monkeypatch.setattr(
        "app.core.pipeline.highlight_detect._compute_audio_energy_scores",
        lambda *args, **kwargs: np.array([9, 9, 1, 8, 1, 7, 1, 6, 1, 5, 1, 4]),
    )
    segments = [
        Segment(start=index * 5, end=(index + 1) * 5, text="discussion")
        for index in range(12)
    ]

    highlights = detect_highlights(
        segments,
        audio_path="unused.wav",
        duration=60,
        window_seconds=5,
        min_clip_seconds=5,
        max_clip_seconds=10,
        top_n=3,
        exclude_before_seconds=10,
        min_separation_seconds=5,
    )

    assert len(highlights) == 3
    assert all(highlight.start >= 10 for highlight in highlights)
    assert highlights[1].start >= highlights[0].end + 5
    assert highlights[2].start >= highlights[1].end + 5
