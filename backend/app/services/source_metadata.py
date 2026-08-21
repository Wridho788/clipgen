"""Read non-sensitive metadata emitted by yt-dlp for hashtag references."""
from __future__ import annotations

import json
import re
from pathlib import Path


def load_youtube_reference_hashtags(source_path: str | Path | None) -> list[str]:
    """Return source video tags/hashtags when yt-dlp's info JSON is available.

    Source tags are a hint, not a guarantee: YouTube does not expose a stable
    channel-level hashtag list for every video.  Callers should label the
    fallback when this file is unavailable.
    """
    if not source_path:
        return []
    path = Path(source_path)
    candidates = [path.with_suffix(".info.json"), path.parent / f"{path.stem}.info.json"]
    info_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if info_path is None:
        return []
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    values: list[str] = []
    raw_tags = info.get("tags", []) if isinstance(info, dict) else []
    if isinstance(raw_tags, list):
        values.extend(str(item) for item in raw_tags)
    description = str(info.get("description", "")) if isinstance(info, dict) else ""
    values.extend(re.findall(r"(?<!\w)#([\w-]+)", description, flags=re.UNICODE))

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = re.sub(r"[^\w-]", "", value.replace("#", "").strip(), flags=re.UNICODE)
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            result.append(tag)
    return result[:10]
