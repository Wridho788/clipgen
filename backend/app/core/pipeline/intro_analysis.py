"""Cheap visual inspection for YouTube intros and pre-made highlight montages."""
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from loguru import logger


@dataclass(frozen=True)
class IntroAnalysis:
    skip_seconds: float
    sampled_seconds: float
    rapid_cut_ratio: float
    montage_detected: bool
    reason: str

    def as_dict(self) -> dict[str, float | bool | str]:
        return asdict(self)


def analyze_youtube_intro(
    source_path: Path,
    duration_seconds: float,
    fallback_skip_seconds: float,
    analysis_seconds: float,
    max_skip_seconds: float,
) -> IntroAnalysis:
    """Extend the normal intro skip only when the opening has rapid scene cuts.

    This is deliberately a lightweight visual heuristic, not a claim of semantic
    AI understanding. It protects long podcasts from their opening montage while
    keeping runtime negligible compared with transcription.
    """
    baseline = max(0.0, min(float(fallback_skip_seconds), float(max_skip_seconds)))
    sample_limit = max(0.0, min(float(duration_seconds), float(analysis_seconds)))
    if sample_limit < 8:
        return IntroAnalysis(baseline, sample_limit, 0.0, False, "intro_default")

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        logger.warning(f"Intro analysis skipped: cannot open {source_path.name}")
        return IntroAnalysis(baseline, sample_limit, 0.0, False, "intro_default_unavailable")

    differences: list[tuple[float, float]] = []
    previous_frame = None
    try:
        for second in range(0, int(sample_limit)):
            capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            success, frame = capture.read()
            if not success:
                continue
            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            thumbnail = cv2.resize(grayscale, (64, 36), interpolation=cv2.INTER_AREA)
            if previous_frame is not None:
                difference = float(np.mean(cv2.absdiff(thumbnail, previous_frame)))
                differences.append((float(second), difference))
            previous_frame = thumbnail
    except cv2.error as error:
        logger.warning(f"Intro analysis skipped for {source_path.name}: {error}")
    finally:
        capture.release()

    if len(differences) < 6:
        return IntroAnalysis(baseline, sample_limit, 0.0, False, "intro_default")

    # A hard cut typically produces a large average difference even after the
    # image is reduced to a thumbnail. The ratio prevents one animated frame
    # from extending the skip range.
    rapid_cuts = [(second, value) for second, value in differences if value >= 28.0]
    cut_ratio = len(rapid_cuts) / len(differences)
    montage_detected = len(rapid_cuts) >= 7 and cut_ratio >= 0.12
    if not montage_detected:
        return IntroAnalysis(baseline, sample_limit, round(cut_ratio, 3), False, "intro_default")

    last_cut_second = rapid_cuts[-1][0]
    skip_seconds = min(float(max_skip_seconds), max(baseline, last_cut_second + 5.0))
    return IntroAnalysis(
        round(skip_seconds, 1),
        sample_limit,
        round(cut_ratio, 3),
        True,
        "intro_montage_visual",
    )
