"""
Clip candidate generation (docs/01 §7, docs/04 §5-6).

``transcript-boundary-v1`` builds windows that start and end on transcript
segment boundaries, so a clip does not open or close mid-sentence. Each window
gets a handful of transparent signals; their weighted sum only *ranks*
candidates inside one job. It is not a probability and not a view forecast.

Coverage across the source is preserved (the earlier evenly spaced behaviour):
the timeline is split into one region per requested clip and the best
non-overlapping window is taken from each region.

When no transcript exists the ``even-spacing-v1`` fallback reproduces the
previous evenly spaced windows and says so in the explanation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.timeline import TimedSegment

TRANSCRIPT_ALGORITHM = "transcript-boundary-v1"
FALLBACK_ALGORITHM = "even-spacing-v1"

# Relative weights. Documented in docs/10-implementation-notes.md; change the
# algorithm version whenever these change so evaluations stay comparable.
SIGNAL_WEIGHTS: dict[str, float] = {
    "complete_ending": 0.30,
    "standalone_opening": 0.20,
    "opening_hook": 0.20,
    "speech_coverage": 0.20,
    "duration_fit": 0.10,
}

LEAD_IN_MS = 150
TAIL_MS = 300

_HOOK_PATTERNS = [
    r"\?",
    r"\b(why|how|what if|here is|here's|the truth|the secret|the mistake|never|nobody|everyone|the problem|remember)\b",
    r"\b(kenapa|mengapa|bagaimana|gimana|rahasia|kesalahan|jangan|tidak ada yang|semua orang|masalahnya|ingat)\b",
]
_CONNECTOR_START = re.compile(
    r"^(and|but|so|because|or|then|also|which|that|dan|tapi|tetapi|jadi|karena|atau|terus|lalu|yang|bahwa)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[.!?…]['\")\]]*$")


@dataclass
class Candidate:
    start_ms: int
    end_ms: int
    signals: dict[str, float]
    score: float
    explanation: list[str]
    algorithm_version: str
    text: str = ""
    rank: int = 0
    total: int = 0
    segment_range: tuple[int, int] | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def analysis(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "rank": self.rank,
            "total": self.total,
            "score": round(self.score, 4),
            "score_meaning": "Peringkat relatif di dalam job ini, bukan prediksi views atau viralitas.",
            "signals": {key: round(value, 3) for key, value in self.signals.items()},
            "explanation": self.explanation,
            **self.metadata,
        }


def generate_candidates(
    segments: list[TimedSegment],
    *,
    duration_ms: int,
    min_ms: int,
    max_ms: int,
    count: int,
) -> list[Candidate]:
    """Return ``count`` (or fewer) non-overlapping candidates ordered by start."""
    if duration_ms <= 0 or count <= 0:
        return []
    min_ms = max(1_000, min(min_ms, max_ms))
    windows = _transcript_windows(segments, duration_ms=duration_ms, min_ms=min_ms, max_ms=max_ms)
    if not windows:
        return even_spacing_candidates(duration_ms=duration_ms, max_ms=max_ms, count=count)

    selected = _select_with_coverage(windows, duration_ms=duration_ms, count=count)
    by_score = sorted(selected, key=lambda item: item.score, reverse=True)
    for rank, candidate in enumerate(by_score, start=1):
        candidate.rank = rank
        candidate.total = len(selected)
    return sorted(selected, key=lambda item: item.start_ms)


def even_spacing_candidates(*, duration_ms: int, max_ms: int, count: int) -> list[Candidate]:
    count = max(1, count)
    clip_ms = min(max_ms, duration_ms // count) if count > 1 else min(max_ms, duration_ms)
    if clip_ms <= 0:
        return []
    if count <= 1:
        starts = [0]
    else:
        last_start = max(0, duration_ms - clip_ms)
        starts = [int(round(last_start * index / (count - 1))) for index in range(count)]
    candidates = []
    for index, start in enumerate(starts, start=1):
        candidates.append(
            Candidate(
                start_ms=start,
                end_ms=min(duration_ms, start + clip_ms),
                signals={},
                score=0.0,
                explanation=[
                    "Tidak ada transkrip yang bisa dipakai; jendela dibagi rata sepanjang video.",
                    "Batas klip belum menyesuaikan kalimat — periksa awal dan akhir sebelum export.",
                ],
                algorithm_version=FALLBACK_ALGORITHM,
                rank=index,
                total=len(starts),
            )
        )
    return candidates


def _transcript_windows(
    segments: list[TimedSegment],
    *,
    duration_ms: int,
    min_ms: int,
    max_ms: int,
) -> list[Candidate]:
    usable = [segment for segment in segments if segment.text.strip() and segment.end_ms > segment.start_ms]
    windows: list[Candidate] = []
    target_ms = (min_ms + max_ms) / 2
    for first in range(len(usable)):
        start_ms = max(0, usable[first].start_ms - LEAD_IN_MS)
        speech_ms = 0
        texts: list[str] = []
        for last in range(first, len(usable)):
            segment = usable[last]
            end_ms = min(duration_ms, segment.end_ms + TAIL_MS)
            if end_ms - start_ms > max_ms:
                break
            speech_ms += segment.duration_ms
            texts.append(segment.text.strip())
            if end_ms - start_ms < min_ms:
                continue
            window_ms = end_ms - start_ms
            signals = _signals(
                opening=usable[first].text,
                ending=segment.text,
                speech_ms=speech_ms,
                window_ms=window_ms,
                target_ms=target_ms,
                spread_ms=max(1.0, (max_ms - min_ms) / 2),
            )
            score = sum(SIGNAL_WEIGHTS[name] * value for name, value in signals.items())
            windows.append(
                Candidate(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    signals=signals,
                    score=score,
                    explanation=_explain(signals),
                    algorithm_version=TRANSCRIPT_ALGORITHM,
                    text=" ".join(texts),
                    segment_range=(first, last),
                )
            )
    return windows


def _signals(
    *,
    opening: str,
    ending: str,
    speech_ms: int,
    window_ms: int,
    target_ms: float,
    spread_ms: float,
) -> dict[str, float]:
    opening = opening.strip()
    return {
        "complete_ending": 1.0 if _SENTENCE_END.search(ending.strip()) else 0.2,
        "standalone_opening": 0.3 if _CONNECTOR_START.match(opening) else 1.0,
        "opening_hook": 1.0 if any(re.search(pattern, opening, re.IGNORECASE) for pattern in _HOOK_PATTERNS) else 0.0,
        "speech_coverage": max(0.0, min(1.0, speech_ms / max(1, window_ms))),
        "duration_fit": max(0.0, 1.0 - abs(window_ms - target_ms) / (spread_ms * 2)),
    }


def _explain(signals: dict[str, float]) -> list[str]:
    reasons = []
    if signals["opening_hook"] >= 1.0:
        reasons.append("Dibuka dengan pertanyaan atau kalimat pemancing.")
    if signals["standalone_opening"] < 1.0:
        reasons.append("Kalimat pembuka diawali kata sambung — konteks sebelumnya mungkin kurang.")
    else:
        reasons.append("Dimulai di awal kalimat transkrip.")
    if signals["complete_ending"] >= 1.0:
        reasons.append("Berakhir di akhir kalimat.")
    else:
        reasons.append("Akhir klip mungkin memotong kalimat.")
    coverage = signals["speech_coverage"]
    reasons.append(f"{round(coverage * 100)}% durasi berisi ucapan.")
    return reasons


def _select_with_coverage(windows: list[Candidate], *, duration_ms: int, count: int) -> list[Candidate]:
    count = max(1, count)
    region_ms = duration_ms / count
    selected: list[Candidate] = []

    def overlaps(candidate: Candidate) -> bool:
        return any(candidate.start_ms < other.end_ms and other.start_ms < candidate.end_ms for other in selected)

    for region in range(count):
        region_start = region * region_ms
        region_end = region_start + region_ms
        in_region = [
            window for window in windows
            if region_start <= window.start_ms < region_end and not overlaps(window)
        ]
        if in_region:
            selected.append(max(in_region, key=lambda window: (window.score, -window.start_ms)))

    # Short sources can leave regions empty; fill from the global ranking.
    for window in sorted(windows, key=lambda item: item.score, reverse=True):
        if len(selected) >= count:
            break
        if not overlaps(window):
            selected.append(window)
    return selected
