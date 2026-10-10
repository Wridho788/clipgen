"""
Real FFmpeg renders against the legally clean fixtures in tests/fixtures/media.

These are the preview/export parity checks from docs/05 §4: dimensions,
duration within tolerance, audio presence, caption burn-in, atomic publish.
Skipped automatically where ffmpeg/ffprobe are not installed.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.edit_model import AudioSettings, CaptionCue, CaptionSettings, CaptionStyle, ClipEdit
from app.core.errors import ErrorCode, PipelineError
from app.services import clip_render_service
from app.services.export_validation import validate_export
from app.services.media_probe import probe_media

FIXTURES = Path(__file__).parent / "fixtures" / "media"
pytestmark = [
    pytest.mark.media,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
        reason="ffmpeg/ffprobe not installed",
    ),
]


@pytest.fixture
def storage(monkeypatch, tmp_path):
    temp_dir, clips_dir = tmp_path / "temp", tmp_path / "clips"
    monkeypatch.setattr(clip_render_service.settings, "temp_dir", temp_dir)
    monkeypatch.setattr(clip_render_service.settings, "clips_dir", clips_dir)
    monkeypatch.setattr(clip_render_service, "select_video_encoder", lambda acceleration="auto": "libx264")
    return temp_dir, clips_dir


def _render(edit: ClipEdit, source_name: str = "speech_landscape.mp4", clip_id: str = "clip"):
    source = FIXTURES / source_name
    facts = probe_media(source)
    assert facts is not None
    return clip_render_service.render_edit_to_file(
        source_path=source, source=facts, edit=edit, clip_id=clip_id, revision=1,
    )


def _gray_frame(path: Path, at_seconds: float) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(at_seconds), "-i", str(path), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    ).stdout


def test_probe_media_reads_fixture_facts():
    facts = probe_media(FIXTURES / "speech_landscape.mp4")
    assert (facts.width, facts.height, facts.has_audio) == (480, 270, True)
    assert facts.duration_seconds > 90
    assert probe_media(FIXTURES / "no_audio.mp4").has_audio is False
    assert probe_media(FIXTURES / "corrupt.mp4") is None


def test_vertical_export_with_captions_is_validated(storage):
    temp_dir, clips_dir = storage
    edit = ClipEdit(
        trim_start_ms=10_000, trim_end_ms=16_000, output_preset="tiktok", visual_style="crop",
        watermark_enabled=False,
        captions=CaptionSettings(enabled=True, cues=[CaptionCue(start_ms=10_500, end_ms=15_500, text="Ship one small thing")]),
    )
    outcome = _render(edit)
    validation = outcome.report["validation"]
    assert validation["ok"] is True, validation["problems"]
    assert (validation["width"], validation["height"]) == (1080, 1920)
    assert abs(validation["duration_seconds"] - 6.0) <= 0.35
    assert validation["has_audio"] is True
    assert outcome.report["captions_rendered"] == 1
    assert outcome.path == clips_dir / "clip_r1.mp4"
    assert list(temp_dir.iterdir()) == []  # partial file and ASS cleaned up


def test_burned_caption_appears_at_the_saved_position(storage):
    style = CaptionStyle(font_size=90, background="box", position_y=0.8, text_color="#FFFFFF", background_color="#000000")
    base = dict(trim_start_ms=20_000, trim_end_ms=25_000, output_preset="original", watermark_enabled=False)
    cue = CaptionCue(start_ms=20_000, end_ms=25_000, text="CAPTION TEST")
    with_caption = _render(ClipEdit(**base, captions=CaptionSettings(enabled=True, style=style, cues=[cue])), clip_id="with")
    without = _render(ClipEdit(**base), clip_id="without")

    width, height = 480, 270
    a = _gray_frame(with_caption.path, 2.0)
    b = _gray_frame(without.path, 2.0)
    assert len(a) == len(b) == width * height

    def band_difference(center_fraction: float) -> float:
        center = int(center_fraction * height)
        rows = range(max(0, center - 8), min(height, center + 8))
        total = sum(abs(a[row * width + col] - b[row * width + col]) for row in rows for col in range(width // 4, 3 * width // 4))
        return total / (len(rows) * (width // 2))

    assert band_difference(0.8) > 15  # caption box drawn where the edit placed it
    assert band_difference(0.2) < 3  # rest of the frame unchanged


def test_source_without_audio_exports_without_audio(storage):
    outcome = _render(
        ClipEdit(trim_start_ms=0, trim_end_ms=6_000, output_preset="square", watermark_enabled=False),
        source_name="no_audio.mp4",
    )
    validation = outcome.report["validation"]
    assert validation["ok"] is True and validation["has_audio"] is False
    assert (validation["width"], validation["height"]) == (1080, 1080)


def test_muted_export_drops_audio(storage):
    outcome = _render(ClipEdit(
        trim_start_ms=0, trim_end_ms=5_000, output_preset="original", watermark_enabled=False,
        audio=AudioSettings(enabled=False),
    ))
    assert outcome.report["validation"]["has_audio"] is False


def test_failed_render_publishes_nothing(storage, monkeypatch):
    temp_dir, clips_dir = storage
    monkeypatch.setattr(clip_render_service, "select_video_encoder", lambda acceleration="auto": "no_such_encoder")
    edit = ClipEdit(trim_start_ms=0, trim_end_ms=5_000, output_preset="original", watermark_enabled=False)
    with pytest.raises(PipelineError) as error:
        _render(edit)
    assert error.value.code == ErrorCode.EXPORT_FAILED
    assert not clips_dir.exists() or list(clips_dir.iterdir()) == []
    assert list(temp_dir.iterdir()) == []


def test_validation_reports_mismatches():
    result = validate_export(
        FIXTURES / "no_audio.mp4", expected_width=1080, expected_height=1920,
        expected_duration_seconds=3.0, expects_audio=True,
    )
    assert result.ok is False
    assert result.checks["dimensions"] is False and result.checks["duration"] is False and result.checks["audio"] is False
    assert len(result.problems) == 3
    missing = validate_export(
        FIXTURES / "missing.mp4", expected_width=1, expected_height=1, expected_duration_seconds=1, expects_audio=False,
    )
    assert missing.ok is False and missing.checks == {"exists": False}
