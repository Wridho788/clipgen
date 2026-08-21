from pathlib import Path
from types import SimpleNamespace

from app.core.pipeline import social_render
from app.core.pipeline.highlight_detect import _context_score
from app.core.pipeline.subtitle_burn import _write_ass
from app.core.pipeline.transcribe import Segment, Word


def test_blur_filter_creates_background_and_foreground_layers():
    filter_graph = social_render._blur_background_filter(1080, 1920)

    assert "split=2" in filter_graph
    assert "boxblur" in filter_graph
    assert "overlay=(W-w)/2:(H-h)/2" in filter_graph


def test_context_score_prefers_payoff_or_emotional_moments():
    assert _context_score("Akhirnya hasilnya bikin semua terharu!") > _context_score("Hari ini kita mulai dari awal.")


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


def test_karaoke_ass_has_word_highlight_and_hook(tmp_path):
    subtitle_file = tmp_path / "subtitle.ass"
    _write_ass(
        subtitle_file,
        [
            Segment(
                0,
                1,
                "Ini payoff",
                [Word(0, 0.5, "Ini"), Word(0.5, 1, "payoff")],
            )
        ],
        "karaoke",
        "Jangan skip",
        10,
    )

    content = subtitle_file.read_text(encoding="utf-8")
    assert "Style: Hook" in content
    assert "Jangan skip" in content
    assert "\\bord7\\blur3" in content
