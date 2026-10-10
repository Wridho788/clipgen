from pathlib import Path
from types import SimpleNamespace

from app.core.pipeline import social_render


def test_blur_filter_creates_background_and_foreground_layers():
    filter_graph = social_render._blur_background_filter(1080, 1920)

    assert "split=2" in filter_graph
    assert "boxblur" in filter_graph
    assert "overlay=(W-w)/2:(H-h)/2" in filter_graph


def test_social_render_uses_selected_preset_and_style(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(social_render, "select_video_encoder", lambda acceleration: "libx264")
    monkeypatch.setattr(
        social_render,
        "run_ffmpeg_with_fallback",
        lambda command, encoder, **kwargs: commands.append(command) or SimpleNamespace(returncode=0, stderr=""),
    )

    result = social_render.render_social_clip(
        Path("input.mp4"),
        tmp_path,
        "clip-1",
        output_preset="square",
        visual_style="split",
    )

    assert result == tmp_path / "clip-1_rendered.mp4"
    assert any("vstack=inputs=2" in part for part in commands[0])
    assert any("1080:540" in part for part in commands[0])


def test_social_render_seeks_and_limits_when_rendering_directly_from_source(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(social_render, "select_video_encoder", lambda acceleration: "libx264")
    monkeypatch.setattr(
        social_render,
        "run_ffmpeg_with_fallback",
        lambda command, encoder, **kwargs: commands.append(command) or SimpleNamespace(returncode=0, stderr=""),
    )

    social_render.render_social_clip(
        Path("source.mp4"),
        tmp_path,
        "clip-1",
        output_preset="tiktok",
        visual_style="blur",
        start_time=30,
        end_time=60,
    )

    assert commands[0][commands[0].index("-ss") + 1] == "30"
    assert commands[0][commands[0].index("-t") + 1] == "30"
    assert "veryfast" in commands[0]


def test_social_render_can_explicitly_skip_the_default_watermark(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(social_render, "select_video_encoder", lambda acceleration: "libx264")
    monkeypatch.setattr(
        social_render,
        "run_ffmpeg_with_fallback",
        lambda command, encoder, **kwargs: commands.append(command) or SimpleNamespace(returncode=0, stderr=""),
    )

    social_render.render_social_clip(
        Path("source.mp4"),
        tmp_path,
        "clip-clean",
        output_preset="tiktok",
        visual_style="blur",
        watermark_text="",
    )

    assert not any("drawtext=" in part for part in commands[0])
