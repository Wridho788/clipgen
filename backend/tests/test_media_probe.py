import json
import subprocess
from pathlib import Path

import pytest

from app.core.pipeline import audio_extract
from app.services import media_probe


@pytest.mark.parametrize("module,probe", [(media_probe, media_probe.probe_video), (audio_extract, audio_extract.has_audio_stream)])
def test_probe_honors_configured_timeout_and_propagates_timeout(monkeypatch, module, probe):
    monkeypatch.setattr(module.settings, "media_probe_timeout_seconds", 45)

    def run(command, *, capture_output, text, timeout):
        assert timeout == 45
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired):
        probe(Path("video.mp4"))


def test_probe_preserves_video_metadata(monkeypatch):
    payload = {"streams": [{"codec_type": "video", "width": 1920, "height": 1080}], "format": {"duration": "61.5"}}
    monkeypatch.setattr(media_probe.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, json.dumps(payload)))
    info = media_probe.probe_video(Path("video.mp4"))
    assert info == media_probe.VideoInfo(61.5, 1920, 1080)


def test_probe_rejects_invalid_media(monkeypatch):
    monkeypatch.setattr(media_probe.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, ""))
    assert media_probe.probe_video(Path("invalid.mp4")) is None
