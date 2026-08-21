"""Adaptive candidate count planning for automatic short-form jobs."""
from __future__ import annotations


def resolve_clip_count(
    duration_seconds: float | None,
    requested_count: int,
    *,
    minimum: int = 1,
    maximum: int = 12,
) -> int:
    """Respect an explicit count; otherwise derive a sensible candidate count.

    One candidate per roughly eight minutes keeps short videos lightweight while
    letting longer sources surface more than a fixed five moments. Highlight
    scoring can still return fewer clips when the material is weak.
    """
    if requested_count > 0:
        return max(minimum, min(maximum, int(requested_count)))

    duration = max(0.0, float(duration_seconds or 0.0))
    if duration <= 0:
        return minimum
    return max(minimum, min(maximum, round(duration / 480.0)))
