from types import SimpleNamespace

import pytest

from app.services import youtube_downloader
from app.services.youtube_downloader import YouTubeDownloadError, download_youtube_video


def test_download_retries_with_safari_client_for_precondition_failure(monkeypatch, tmp_path):
    commands = []
    output_file = tmp_path / "job-1.mp4"

    def fake_run(command, **kwargs):
        commands.append(command)
        if len(commands) == 1:
            return SimpleNamespace(returncode=1, stderr="ERROR: Precondition check failed", stdout="")
        output_file.write_bytes(b"video")
        return SimpleNamespace(returncode=0, stderr="", stdout=str(output_file))

    monkeypatch.setattr(youtube_downloader.subprocess, "run", fake_run)

    downloaded = download_youtube_video("https://youtu.be/example", tmp_path, "job-1", 30)

    assert downloaded == output_file
    assert "bv*+ba/b" in commands[0]
    assert "--write-info-json" in commands[0]
    assert "--js-runtimes" in commands[0]
    assert "deno" in commands[0]
    assert "--extractor-args" in commands[1]
    assert "youtube:player_client=web_safari" in commands[1]


def test_download_returns_friendly_error_without_unrelated_fallback(monkeypatch, tmp_path):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=1, stderr="ERROR: private video", stdout="")

    monkeypatch.setattr(youtube_downloader.subprocess, "run", fake_run)

    with pytest.raises(YouTubeDownloadError, match="YouTube download gagal"):
        download_youtube_video("https://youtu.be/example", tmp_path, "job-2", 30)

    assert len(commands) == 1
