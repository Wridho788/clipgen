"""Build copy-ready metadata for manual platform distribution.

ClipGen deliberately does not require YouTube or Meta credentials for V1.  The
API returns a small, platform-specific package that a user can copy into the
native upload forms instead.
"""
from __future__ import annotations

import re
from typing import Iterable


def build_distribution_pack(
    title: str | None,
    caption: str | None,
    hashtags: Iterable[str] | None,
    *,
    source_reference_hashtags: Iterable[str] | None = None,
    source_name: str | None = None,
) -> dict[str, object]:
    clean_title = _single_line(title or "Video Menarik")[:100]
    clean_caption = _plain_text(caption or "Tonton klip ini dan bagikan pendapatmu.")[:5000]
    generated_tags = _normalize_tags(hashtags)
    source_tags = _normalize_tags(source_reference_hashtags)
    merged_tags = _dedupe_tags([*source_tags, *generated_tags])[:15]
    hashtag_text = " ".join(f"#{tag}" for tag in merged_tags)
    youtube_description = _truncate(
        "\n\n".join(part for part in (clean_caption, hashtag_text) if part),
        5000,
    )
    youtube_tags = _fit_youtube_tags(merged_tags)
    facebook_caption = _truncate(
        "\n\n".join(part for part in (clean_caption, hashtag_text) if part),
        63206,
    )
    source_label = "youtube_source_tags+clip_metadata" if source_tags else "clip_metadata_fallback"

    return {
        "source_name": source_name,
        "hashtag_source": source_label,
        "youtube": {
            "title": clean_title,
            "description": youtube_description,
            "tags": youtube_tags,
            "hashtags": hashtag_text,
            "checklist": [
                "Upload video sebagai YouTube Short bila durasi dan rasio sudah sesuai.",
                "Tempel title, description, dan tags; periksa audience/copyright sebelum publish.",
                "Atur visibility dan jadwal publikasi secara manual di YouTube Studio.",
            ],
        },
        "facebook": {
            "caption": facebook_caption,
            "hashtags": hashtag_text,
            "checklist": [
                "Upload file pada Reels/video Facebook dengan rasio yang sesuai.",
                "Tempel caption dan hashtags; pilih audience serta thumbnail bila diperlukan.",
                "Publish atau schedule secara manual dari Facebook/Meta Business Suite.",
            ],
        },
    }


def _normalize_tags(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        tag = re.sub(r"[^\w-]", "", str(value).replace("#", "").strip(), flags=re.UNICODE)
        if tag and tag.lower() not in {item.lower() for item in result}:
            result.append(tag)
    return result


def _dedupe_tags(values: Iterable[str]) -> list[str]:
    return _normalize_tags(values)


def _fit_youtube_tags(tags: list[str]) -> list[str]:
    """Keep the list within YouTube's practical 500-character tags field."""
    result: list[str] = []
    total = 0
    for tag in tags:
        extra = len(tag) + (1 if result else 0)
        if total + extra > 500:
            break
        result.append(tag)
        total += extra
    return result


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: max(0, limit - 1)].rstrip() + "…"
