"""Deterministic checks for campaign-specific clipping and distribution rules."""

from __future__ import annotations

import re
from typing import Iterable

from app.schemas import CampaignBrief


def evaluate_campaign_compliance(
    brief: CampaignBrief | None,
    *,
    transcript_text: str = "",
    title: str | None = None,
    caption: str | None = None,
    hashtags: Iterable[str] | None = None,
    duration_seconds: float | None = None,
) -> dict[str, object] | None:
    """Return pass/review/blocked checks without pretending to verify visuals."""
    if brief is None:
        return None

    transcript = transcript_text or ""
    metadata_text = " ".join(value or "" for value in (title, caption))
    normalized_tags = {str(tag).replace("#", "").strip().casefold() for tag in hashtags or []}
    checks: list[dict[str, str]] = []

    if duration_seconds is None:
        checks.append(_check("duration", "Durasi klip", "review_required", "Durasi belum dapat diverifikasi."))
    elif brief.min_clip_seconds <= duration_seconds <= brief.max_clip_seconds:
        checks.append(_check("duration", "Durasi klip", "pass", f"{duration_seconds:.1f} detik sesuai brief."))
    else:
        checks.append(
            _check(
                "duration",
                "Durasi klip",
                "blocked",
                f"{duration_seconds:.1f} detik di luar rentang {brief.min_clip_seconds:g}–{brief.max_clip_seconds:g} detik.",
            )
        )

    for term in brief.prohibited_terms:
        if _contains_term(f"{transcript} {metadata_text}", term):
            checks.append(_check("prohibited_terms", "Kata/tema terlarang", "blocked", f"Menemukan: {term}"))
            break
    else:
        checks.append(_check("prohibited_terms", "Kata/tema terlarang", "pass", "Tidak ada kata terlarang pada transcript/metadata."))

    missing_phrases = [phrase for phrase in brief.required_phrases if phrase.casefold() not in transcript.casefold()]
    if missing_phrases:
        status = "review_required" if brief.allow_voiceover else "blocked"
        detail = "Frasa wajib belum ditemukan: " + ", ".join(missing_phrases)
        if brief.allow_voiceover:
            detail += ". Tambahkan voice-over manual dan review sebelum publish."
        checks.append(_check("required_phrases", "Narasi wajib", status, detail))
    else:
        checks.append(_check("required_phrases", "Narasi wajib", "pass", "Semua frasa wajib ditemukan pada transcript."))

    missing_tags = [tag for tag in brief.hashtags if tag.casefold() not in normalized_tags]
    checks.append(
        _check(
            "hashtags",
            "Hashtag kampanye",
            "review_required" if missing_tags else "pass",
            "Tambahkan: " + ", ".join(f"#{tag}" for tag in missing_tags) if missing_tags else "Hashtag kampanye tersedia.",
        )
    )

    if brief.cta and brief.cta.casefold() not in (caption or "").casefold():
        checks.append(_check("cta", "CTA", "review_required", "CTA kampanye belum ada di caption."))
    elif brief.cta:
        checks.append(_check("cta", "CTA", "pass", "CTA kampanye tersedia."))

    if brief.hook_required:
        checks.append(
            _check(
                "hook",
                "Hook 3 detik pertama",
                "review_required",
                "Perlu review visual untuk memastikan hook kuat di awal klip.",
            )
        )

    if brief.required_visuals:
        checks.append(
            _check(
                "visuals",
                "Kehadiran produk/visual wajib",
                "review_required",
                "Konfirmasi manual: " + "; ".join(brief.required_visuals),
            )
        )

    if brief.source_only:
        checks.append(_check("source_only", "Konten berasal dari source", "review_required", "Pastikan tidak ada footage/narasi tambahan di luar source."))
    if brief.avoid_misleading_edits:
        checks.append(_check("context", "Konteks tidak menyesatkan", "review_required", "Review potongan sebelum publish agar tidak mengubah makna."))

    statuses = {check["status"] for check in checks}
    overall = "blocked" if "blocked" in statuses else "review_required" if "review_required" in statuses else "pass"
    score = round(sum(1 for check in checks if check["status"] == "pass") / max(1, len(checks)) * 100)
    return {"status": overall, "score": score, "checks": checks}


def _contains_term(text: str, term: str) -> bool:
    escaped = re.escape(term.strip())
    return bool(escaped and re.search(rf"(?<!\w){escaped}(?!\w)", text, flags=re.IGNORECASE))


def _check(key: str, label: str, status: str, detail: str) -> dict[str, str]:
    return {"key": key, "label": label, "status": status, "detail": detail}
