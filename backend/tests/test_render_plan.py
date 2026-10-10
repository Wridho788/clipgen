from pathlib import Path

from app.core.edit_model import AudioSettings, CaptionCue, CaptionSettings, CaptionStyle, ClipEdit, Framing
from app.core.pipeline.render_plan import (
    SourceFacts,
    build_ass_document,
    build_render_plan,
    build_video_filter,
    caption_scale,
)

SOURCE = SourceFacts(width=640, height=360, duration_ms=100_000, has_audio=True)


def _edit(**overrides) -> ClipEdit:
    data = {"trim_start_ms": 12_345, "trim_end_ms": 32_345, "output_preset": "tiktok", "visual_style": "crop"}
    data.update(overrides)
    return ClipEdit(**data)


def _plan(edit: ClipEdit, source: SourceFacts = SOURCE, **kwargs):
    return build_render_plan(
        source_path=Path("/src/video.mp4"),
        edit=edit,
        source=source,
        output_path=Path("/tmp/out.partial.mp4"),
        encoder="libx264",
        ass_path=kwargs.get("ass_path"),
        watermark_filter=kwargs.get("watermark_filter"),
    )


def test_plan_seeks_and_limits_duration_from_saved_trim():
    plan = _plan(_edit())
    command = plan.command
    assert command[command.index("-ss") + 1] == "12.345"
    assert command[command.index("-t") + 1] == "20.000"
    assert command.index("-ss") < command.index("-i")
    assert (plan.width, plan.height, plan.duration_ms) == (1080, 1920, 20_000)
    assert command[-1] == "/tmp/out.partial.mp4"
    assert "+faststart" in command


def test_plan_maps_audio_only_when_source_has_it_and_it_is_enabled():
    assert "0:a:0" in _plan(_edit()).command
    muted = _plan(_edit(audio=AudioSettings(enabled=False)))
    assert "-an" in muted.command and muted.expects_audio is False
    silent_source = _plan(_edit(), SourceFacts(640, 360, 100_000, has_audio=False))
    assert "-an" in silent_source.command and silent_source.expects_audio is False
    normalized = _plan(_edit(audio=AudioSettings(normalize=True))).command
    assert normalized[normalized.index("-af") + 1].startswith("loudnorm")


def test_crop_uses_focus_like_css_object_position():
    graph = build_video_filter(
        _edit(framing=Framing(focus_x=0.25, focus_y=0.5)), 1080, 1920, ass_path=None, watermark_filter=None
    )
    assert "force_original_aspect_ratio=increase" in graph
    assert "crop=1080:1920:(iw-ow)*0.2500:(ih-oh)*0.5000" in graph
    assert graph.endswith("[vout]")


def test_zoom_blur_split_and_original_graphs():
    zoom = build_video_filter(_edit(visual_style="zoom"), 1080, 1920, ass_path=None, watermark_filter=None)
    assert "scale=1210:2150" in zoom
    blur = build_video_filter(_edit(visual_style="blur"), 1080, 1920, ass_path=None, watermark_filter=None)
    assert "boxblur" in blur and "overlay" in blur
    split = build_video_filter(_edit(visual_style="split"), 1080, 1920, ass_path=None, watermark_filter=None)
    assert "vstack=inputs=2" in split
    original = _plan(_edit(output_preset="original"), SourceFacts(641, 361, 100_000, True))
    assert (original.width, original.height) == (640, 360)


def test_captions_and_watermark_are_appended_in_order():
    graph = build_video_filter(
        _edit(), 1080, 1920, ass_path=Path("/tmp/c:1.ass"), watermark_filter="drawtext=text='x'"
    )
    tail = graph.split("[base]")[-1]
    assert tail.index("ass=filename='/tmp/c\\:1.ass'") < tail.index("drawtext") < tail.index("format=yuv420p")


def test_ass_document_offsets_cues_to_clip_time_and_applies_style():
    cues = [
        CaptionCue(start_ms=12_000, end_ms=14_000, text="straddles {start}"),
        CaptionCue(start_ms=20_000, end_ms=21_500, text="a fairly long caption that needs wrapping"),
    ]
    style = CaptionStyle(font_size=60, text_color="#FFCC00", background="box", position_y=0.5, max_chars_per_line=20)
    edit = _edit(captions=CaptionSettings(enabled=True, style=style, cues=cues))
    document = build_ass_document(edit, 1080, 1920)
    assert "PlayResX: 1080" in document and "PlayResY: 1920" in document
    assert "Style: Caption,DejaVu Sans,60,&H0000CCFF" in document  # BGR order
    assert ",3,12,0,5," in document  # box border style, padding, centred alignment
    dialogue = [line for line in document.splitlines() if line.startswith("Dialogue")]
    assert dialogue[0].startswith("Dialogue: 0,0:00:00.00,0:00:01.66,")  # clamped to trim start 12.345
    assert "\\{start\\}" in dialogue[0]
    assert "{\\an5\\pos(540,960)}" in dialogue[1]
    assert dialogue[1].count("\\N") == 2  # three wrapped lines


def test_ass_document_scales_font_to_canvas():
    style = CaptionStyle(font_size=64)
    edit = _edit(output_preset="landscape", captions=CaptionSettings(enabled=True, style=style, cues=[
        CaptionCue(start_ms=13_000, end_ms=14_000, text="hi")
    ]))
    assert caption_scale(1920, 1080) == 1.0
    assert "DejaVu Sans,64," in build_ass_document(edit, 1920, 1080)
    assert "DejaVu Sans,32," in build_ass_document(edit, 540, 960)


def test_no_ass_document_without_visible_captions():
    assert build_ass_document(_edit(), 1080, 1920) is None
    assert _plan(_edit()).ass_document is None
