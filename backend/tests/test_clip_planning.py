from app.services.clip_planning import resolve_clip_count


def test_explicit_clip_count_is_respected_within_safety_limit():
    assert resolve_clip_count(3_600, 7) == 7


def test_auto_count_scales_with_source_duration_instead_of_fixed_five():
    assert resolve_clip_count(180, 0) == 1
    assert resolve_clip_count(2_400, 0) == 5
    assert resolve_clip_count(5_760, 0) == 12
