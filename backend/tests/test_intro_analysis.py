from pathlib import Path

import numpy as np

from app.core.pipeline.intro_analysis import analyze_youtube_intro


class _FakeCapture:
    def __init__(self):
        self.index = 0

    def isOpened(self):
        return True

    def set(self, _property, value):
        self.index = int(value / 1000)

    def read(self):
        shade = 255 if self.index % 2 else 0
        return True, np.full((72, 128, 3), shade, dtype=np.uint8)

    def release(self):
        return None


def test_visual_intro_analysis_extends_skip_for_rapid_cut_montage(monkeypatch):
    monkeypatch.setattr(
        "app.core.pipeline.intro_analysis.cv2.VideoCapture",
        lambda _path: _FakeCapture(),
    )

    result = analyze_youtube_intro(
        Path("unused.mp4"),
        duration_seconds=120,
        fallback_skip_seconds=60,
        analysis_seconds=90,
        max_skip_seconds=90,
    )

    assert result.montage_detected is True
    assert result.skip_seconds > 60
    assert result.reason == "intro_montage_visual"
