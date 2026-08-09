from pathlib import Path

import pytest

from app.core.pipeline import audio_extract


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_has_audio_stream_detects_audio(monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return FakeCompletedProcess(stdout="audio\n")

    monkeypatch.setattr(audio_extract.subprocess, "run", fake_run)

    assert audio_extract.has_audio_stream(Path("video.mp4")) is True


def test_extract_audio_fails_cleanly_when_video_has_no_audio(monkeypatch, tmp_path):
    monkeypatch.setattr(audio_extract, "has_audio_stream", lambda path: False)

    with pytest.raises(RuntimeError, match="tidak punya audio track"):
        audio_extract.extract_audio(tmp_path / "video.mp4", tmp_path)


def test_extract_audio_maps_first_audio_stream(monkeypatch, tmp_path):
    video_path = tmp_path / "video.mp4"
    captured = {}

    monkeypatch.setattr(audio_extract, "has_audio_stream", lambda path: True)

    def fake_run(cmd, capture_output, text):
        captured["cmd"] = cmd
        return FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(audio_extract.subprocess, "run", fake_run)

    output_path = audio_extract.extract_audio(video_path, tmp_path)

    assert output_path == tmp_path / "video_audio.wav"
    assert "-map" in captured["cmd"]
    assert "0:a:0" in captured["cmd"]
