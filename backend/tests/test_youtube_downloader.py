from types import SimpleNamespace

import pytest

from app.services import youtube_downloader
from app.services.youtube_downloader import YouTubeDownloadError, download_youtube_video


def test_download_retries_with_documented_client_for_precondition_failure(monkeypatch, tmp_path):
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
    assert "bv*[height<=720]+ba/b[height<=720]" in commands[0]
    fragments_index = commands[0].index("--concurrent-fragments")
    assert commands[0][fragments_index + 1] == "4"
    assert "--write-info-json" in commands[0]
    assert "--js-runtimes" in commands[0]
    assert "deno" in commands[0]
    assert "--extractor-args" in commands[1]
    assert "youtube:player_client=default,-visionos" in commands[1]


def test_download_retries_after_http_403_before_failing(monkeypatch, tmp_path):
    commands = []
    output_file = tmp_path / "job-403.mp4"

    def fake_run(command, **kwargs):
        commands.append(command)
        if len(commands) == 1:
            return SimpleNamespace(
                returncode=1,
                stderr="ERROR: unable to download video data: HTTP Error 403: Forbidden",
                stdout="",
            )
        output_file.write_bytes(b"video")
        return SimpleNamespace(returncode=0, stderr="", stdout=str(output_file))

    monkeypatch.setattr(youtube_downloader.subprocess, "run", fake_run)

    downloaded = download_youtube_video("https://youtu.be/example", tmp_path, "job-403", 30)

    assert downloaded == output_file
    assert len(commands) == 2
    assert "youtube:player_client=default,-visionos" in commands[1]
    assert "--http-chunk-size" in commands[0]


def test_download_uses_optional_cookie_file_and_user_agent(monkeypatch, tmp_path):
    output_file = tmp_path / "job-cookie.mp4"
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        output_file.write_bytes(b"video")
        return SimpleNamespace(returncode=0, stderr="", stdout=str(output_file))

    monkeypatch.setattr(youtube_downloader.subprocess, "run", fake_run)

    download_youtube_video(
        "https://youtu.be/example",
        tmp_path,
        "job-cookie",
        30,
        cookies_path=cookie_file,
        user_agent="Mozilla/5.0 test",
    )

    assert commands[0][commands[0].index("--cookies") + 1] == str(cookie_file)
    assert commands[0][commands[0].index("--user-agent") + 1] == "Mozilla/5.0 test"


def test_download_returns_friendly_error_without_unrelated_fallback(monkeypatch, tmp_path):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=1, stderr="ERROR: private video", stdout="")

    monkeypatch.setattr(youtube_downloader.subprocess, "run", fake_run)

    with pytest.raises(YouTubeDownloadError, match="YouTube download gagal"):
        download_youtube_video("https://youtu.be/example", tmp_path, "job-2", 30)

    assert len(commands) == 1


def test_download_can_keep_best_available_quality(monkeypatch, tmp_path):
    output_file = tmp_path / "job-3.mp4"
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        output_file.write_bytes(b"video")
        return SimpleNamespace(returncode=0, stderr="", stdout=str(output_file))

    monkeypatch.setattr(youtube_downloader.subprocess, "run", fake_run)

    download_youtube_video(
        "https://youtu.be/example",
        tmp_path,
        "job-3",
        30,
        concurrent_fragments=8,
        max_height=0,
    )

    assert "bv*+ba/b" in commands[0]
    fragments_index = commands[0].index("--concurrent-fragments")
    assert commands[0][fragments_index + 1] == "8"
