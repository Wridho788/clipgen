from app.core.timeline import TimedSegment
from app.services.candidates import (
    FALLBACK_ALGORITHM,
    TRANSCRIPT_ALGORITHM,
    generate_candidates,
)


def _podcast(segment_seconds: int = 6, count: int = 30) -> list[TimedSegment]:
    lines = [
        "Why do most side projects never launch?",
        "and then we kept going for a while",
        "The honest answer is that people never finish.",
        "So here is the secret nobody tells you.",
        "because it was late",
        "Ship one small thing every week.",
    ]
    segments = []
    for index in range(count):
        start = index * segment_seconds * 1000
        segments.append(TimedSegment(start + 200, start + segment_seconds * 1000 - 300, lines[index % len(lines)]))
    return segments


def test_candidates_start_and_end_on_transcript_boundaries():
    segments = _podcast()
    candidates = generate_candidates(segments, duration_ms=180_000, min_ms=15_000, max_ms=30_000, count=3)
    assert len(candidates) == 3
    starts = {segment.start_ms for segment in segments}
    ends = {segment.end_ms for segment in segments}
    for candidate in candidates:
        assert candidate.algorithm_version == TRANSCRIPT_ALGORITHM
        assert candidate.start_ms + 150 in starts or candidate.start_ms == 0
        assert min(candidate.end_ms - 300, 180_000) in ends or candidate.end_ms == 180_000
        assert 15_000 <= candidate.duration_ms <= 30_000


def test_candidates_do_not_overlap_and_cover_the_timeline():
    candidates = generate_candidates(_podcast(), duration_ms=180_000, min_ms=15_000, max_ms=30_000, count=3)
    for left, right in zip(candidates, candidates[1:]):
        assert left.end_ms <= right.start_ms
    # Coverage: one candidate per third of the source.
    regions = {int(candidate.start_ms // 60_000) for candidate in candidates}
    assert regions == {0, 1, 2}


def test_candidates_prefer_complete_standalone_openings_and_explain_why():
    candidates = generate_candidates(_podcast(), duration_ms=180_000, min_ms=15_000, max_ms=30_000, count=3)
    for candidate in candidates:
        assert not candidate.text.lower().startswith(("and ", "because "))
        assert candidate.signals["complete_ending"] == 1.0
        assert any("akhir kalimat" in reason for reason in candidate.explanation)
        analysis = candidate.analysis()
        assert "bukan prediksi" in analysis["score_meaning"]
        assert 1 <= analysis["rank"] <= analysis["total"] == 3


def test_ranks_are_unique_and_follow_score():
    candidates = generate_candidates(_podcast(), duration_ms=180_000, min_ms=15_000, max_ms=30_000, count=3)
    by_rank = sorted(candidates, key=lambda item: item.rank)
    assert [item.rank for item in by_rank] == [1, 2, 3]
    assert by_rank[0].score >= by_rank[1].score >= by_rank[2].score


def test_without_transcript_falls_back_to_even_spacing_and_says_so():
    candidates = generate_candidates([], duration_ms=120_000, min_ms=10_000, max_ms=30_000, count=3)
    assert [(c.start_ms, c.end_ms) for c in candidates] == [(0, 30_000), (45_000, 75_000), (90_000, 120_000)]
    assert all(c.algorithm_version == FALLBACK_ALGORITHM for c in candidates)
    assert "dibagi rata" in candidates[0].explanation[0]


def test_short_source_fills_from_global_ranking_without_overlap():
    segments = _podcast(segment_seconds=5, count=8)  # 40 s of speech
    candidates = generate_candidates(segments, duration_ms=40_000, min_ms=10_000, max_ms=20_000, count=4)
    assert 1 <= len(candidates) <= 4
    for left, right in zip(candidates, candidates[1:]):
        assert left.end_ms <= right.start_ms


def test_long_source_candidate_generation_is_fast_enough():
    import time

    segments = _podcast(segment_seconds=4, count=1500)  # ~100 minutes
    started = time.perf_counter()
    candidates = generate_candidates(segments, duration_ms=6_000_000, min_ms=15_000, max_ms=60_000, count=12)
    assert len(candidates) == 12
    assert time.perf_counter() - started < 5


def test_real_whisper_transcript_fixture_produces_sentence_aligned_candidates():
    """The fixture transcript is real faster-whisper output, including a
    hallucinated repeat whose timestamps run past the end of the audio."""
    import json
    from pathlib import Path

    from app.core.timeline import normalize_segments

    raw = json.loads((Path(__file__).parent / "fixtures/media/speech_landscape.transcript.json").read_text())
    duration_ms = 103_867
    segments, report = normalize_segments(raw, duration_ms)
    assert report.dropped_invalid >= 1 and report.clamped >= 1
    assert all(segment.end_ms <= duration_ms for segment in segments)

    candidates = generate_candidates(segments, duration_ms=duration_ms, min_ms=15_000, max_ms=30_000, count=3)
    assert len(candidates) == 3
    boundaries_start = {max(0, segment.start_ms - 150) for segment in segments}
    boundaries_end = {min(duration_ms, segment.end_ms + 300) for segment in segments}
    for candidate in candidates:
        assert candidate.start_ms in boundaries_start
        assert candidate.end_ms in boundaries_end
        assert candidate.signals["complete_ending"] == 1.0
