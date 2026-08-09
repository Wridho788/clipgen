"""
Stage 3: Highlight detection.

PENTING (transparansi, sesuai diskusi sebelumnya): ini BUKAN "AI viral
prediction". Ini rule-based scoring dari sinyal terukur:
  1. Audio energy spike (RMS relatif terhadap baseline)
  2. Exclamation/laughter cue dari teks transkrip
  3. Speech rate change (kata per detik, perubahan mendadak)

Skor dijumlah berbobot, window bersebelahan dengan skor tinggi
digabung jadi satu clip. Semua bobot ada di config supaya bisa
di-tuning tanpa ubah logika inti.
"""
import re
from dataclasses import dataclass

import numpy as np
import librosa
from loguru import logger

from app.config import settings
from app.core.pipeline.transcribe import Segment

# Kata/pola yang mengindikasikan reaksi kuat (bisa ditambah/disesuaikan)
LAUGH_PATTERNS = re.compile(r"\b(haha+|wkwk+|hehe+|lol)\b", re.IGNORECASE)
EXCLAMATION_PATTERN = re.compile(r"!{1,}")


@dataclass
class Highlight:
    start: float
    end: float
    score: float


def _compute_audio_energy_scores(audio_path, window_seconds: float, duration: float) -> np.ndarray:
    """RMS energy per window, dinormalisasi terhadap baseline (median)."""
    y, sr = librosa.load(str(audio_path), sr=None)
    hop_length = int(sr * window_seconds)
    rms = librosa.feature.rms(y=y, frame_length=hop_length * 2, hop_length=hop_length)[0]

    baseline = np.median(rms) + 1e-8
    normalized = rms / baseline
    return normalized


def _segment_text_score(text: str) -> float:
    score = 0.0
    if LAUGH_PATTERNS.search(text):
        score += 2.0
    n_exclaim = len(EXCLAMATION_PATTERN.findall(text))
    score += min(n_exclaim * 0.5, 2.0)  # cap supaya tidak dominan
    return score


def detect_highlights(
    segments: list[Segment],
    audio_path,
    duration: float,
    window_seconds: float | None = None,
    min_clip_seconds: float | None = None,
    max_clip_seconds: float | None = None,
    top_n: int | None = None,
    exclude_before_seconds: float = 0,
    min_separation_seconds: float = 0,
) -> list[Highlight]:
    """
    Gabungkan skor audio energy + skor teks per window, ranking,
    lalu gabungkan window berdekatan jadi klip 15-60 detik.
    """
    if not segments or duration <= 0:
        logger.warning("No transcript segments/duration, skip highlight detection")
        return []

    window = window_seconds or settings.highlight_window_seconds
    min_duration = min_clip_seconds or settings.highlight_min_clip_seconds
    max_duration = max_clip_seconds or settings.highlight_max_clip_seconds
    requested_top_n = top_n or settings.highlight_top_n
    n_windows = max(1, int(np.ceil(duration / window)))

    try:
        energy_scores = _compute_audio_energy_scores(audio_path, window, duration)
    except Exception as e:
        logger.warning(f"Audio energy analysis gagal, fallback ke skor 0: {e}")
        energy_scores = np.zeros(n_windows)

    # Skor teks per window: cari segmen transkrip yang overlap dengan window itu
    text_scores = np.zeros(n_windows)
    for seg in segments:
        window_idx = int(seg.start // window)
        if 0 <= window_idx < n_windows:
            text_scores[window_idx] += _segment_text_score(seg.text)

    # Samakan panjang array (audio energy windowing bisa beda jumlah dari n_windows)
    min_len = min(len(energy_scores), len(text_scores))
    combined = energy_scores[:min_len] * 1.0 + text_scores[:min_len] * 1.5

    # The beginning of long-form YouTube videos often contains an intro or a
    # pre-made highlight montage. Automatic mode can exclude that range while
    # preserving the existing manual detector behavior by leaving this at zero.
    excluded_before = max(0.0, float(exclude_before_seconds))
    eligible_indices = [
        index for index in range(len(combined))
        if index * window >= excluded_before
    ]
    if not eligible_indices:
        logger.warning("No eligible windows left after intro exclusion")
        return []

    # Keep a broad candidate pool. This lets the distinct-selection fallback
    # return several clips instead of collapsing around one energetic moment.
    ranked_indices = sorted(eligible_indices, key=lambda index: combined[index], reverse=True)
    top_indices = sorted(ranked_indices[: requested_top_n * 8])

    # Gabungkan window bersebelahan jadi satu highlight
    highlights: list[Highlight] = []
    current_start = None
    current_end = None
    current_score_sum = 0.0

    for idx in top_indices:
        w_start = idx * window
        w_end = w_start + window
        if current_start is None:
            current_start, current_end, current_score_sum = w_start, w_end, combined[idx]
        elif w_start - current_end <= window:  # bersebelahan/dekat
            current_end = w_end
            current_score_sum += combined[idx]
        else:
            highlights.append(Highlight(current_start, current_end, current_score_sum))
            current_start, current_end, current_score_sum = w_start, w_end, combined[idx]

    if current_start is not None:
        highlights.append(Highlight(current_start, current_end, current_score_sum))

    # Clamp durasi ke batas min/max, buang yang terlalu pendek
    clamped = []
    for h in highlights:
        dur = h.end - h.start
        if dur < min_duration:
            # perpanjang simetris sampai minimum
            extra = (min_duration - dur) / 2
            h.start = max(excluded_before, h.start - extra)
            h.end = min(duration, h.end + extra)
            # Preserve the requested minimum whenever there is room after the
            # excluded intro range.
            if h.end - h.start < min_duration:
                h.start = max(excluded_before, h.end - min_duration)
        elif dur > max_duration:
            h.end = h.start + max_duration
        clamped.append(h)

    # Ranking final, ambil top_n sesuai config
    clamped.sort(key=lambda h: h.score, reverse=True)
    result = _select_distinct_highlights(
        clamped,
        requested_top_n,
        min_separation_seconds,
    )

    # When high-energy windows are concentrated in one moment, fill remaining
    # slots with non-overlapping candidates from the rest of the episode.
    if len(result) < requested_top_n:
        fallback_candidates = []
        for index in ranked_indices:
            center = (index * window) + (window / 2)
            start = max(excluded_before, center - (min_duration / 2))
            end = min(duration, start + min_duration)
            start = max(excluded_before, end - min_duration)
            if end - start < min_duration:
                continue
            fallback_candidates.append(Highlight(start, end, float(combined[index])))
        result = _select_distinct_highlights(
            [*result, *fallback_candidates],
            requested_top_n,
            min_separation_seconds,
        )

    result.sort(key=lambda h: h.start)  # urutkan lagi berdasarkan waktu untuk output yang enak dibaca

    logger.info(f"Detected {len(result)} highlights dari {n_windows} window dianalisis")
    return result


def _select_distinct_highlights(
    candidates: list[Highlight],
    requested_top_n: int,
    min_separation_seconds: float,
) -> list[Highlight]:
    """Pick strongest clips that do not overlap or crowd one another."""
    selected: list[Highlight] = []
    gap = max(0.0, float(min_separation_seconds))

    for candidate in sorted(candidates, key=lambda h: h.score, reverse=True):
        is_separate = all(
            candidate.end + gap <= selected_highlight.start
            or candidate.start >= selected_highlight.end + gap
            for selected_highlight in selected
        )
        if is_separate:
            selected.append(candidate)
        if len(selected) == requested_top_n:
            break

    return selected
