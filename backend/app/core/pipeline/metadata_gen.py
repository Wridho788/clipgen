"""
Stage 7: Generate metadata (title, caption, hashtags) menggunakan Ollama lokal.

Ollama setup:
  1. Download Ollama dari ollama.ai
  2. ollama pull llama3.2
  3. Ollama server jalan di localhost:11434

API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""
import json
import re

import requests
from loguru import logger

from app.config import settings


def generate_metadata(transcript_text: str, language: str = "id") -> dict:
    """
    Generate title, caption, dan hashtag dari transcript.
    
    Args:
        transcript_text: teks transkrip dari klip (15-60 detik, ~50-150 kata)
    
    Return:
        {
            "title": str,
            "caption": str,
            "hashtags": list[str]
        }
    """
    language = _normalize_language(language)
    defaults = _default_metadata(language)
    if not transcript_text or len(transcript_text.strip()) < 10:
        logger.warning("Transcript terlalu pendek, return default metadata")
        return defaults

    try:
        response = _call_ollama(transcript_text, language)
        parsed = _parse_response(response, language)
        return parsed
    except Exception as e:
        logger.error(f"Metadata generation error: {e}")
        # Fallback: extract title dari first sentence
        first_sentence = transcript_text.split(".")[0][:50]
        return {
            "title": first_sentence or defaults["title"],
            "caption": transcript_text[:100],
            "hashtags": ["content"],
        }


def _call_ollama(transcript_text: str, language: str = "id") -> str:
    """Call Ollama API untuk generate metadata."""
    language = _normalize_language(language)
    if language == "en":
        prompt = f"""Extract social media metadata from this audio segment in English:

Transcript:
{transcript_text}

Return JSON only with these fields:
- title (5-10 catchy, memorable words)
- caption (30-50 words that describe the content and invite engagement)
- hashtags (a list of 5-7 relevant hashtags, without the # symbol)

JSON only, with no additional text."""
    else:
        prompt = f"""Extract metadata dari segment audio ini dalam Bahasa Indonesia:

Transkrip:
{transcript_text}

Berikan response dalam format JSON dengan field:
- title (5-10 kata, catchy, memorable, bisa pake emoji)
- caption (30-50 kata, deskripsi konten, ajakan engage)
- hashtags (list 5-7 hashtag relevan, tanpa simbol #)

JSON saja, tanpa teks tambahan."""

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": settings.ollama_num_predict,
        },
    }

    logger.info(f"Calling Ollama: {settings.ollama_base_url}/api/generate")
    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json=payload,
        timeout=settings.ollama_timeout_seconds,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama API error {response.status_code}: {response.text[:200]}"
        )

    result = response.json()
    return result.get("response", "")


def _parse_response(response_text: str, language: str = "id") -> dict:
    """Parse Ollama response, extract JSON."""
    # Ollama bisa return teks yang diawali "Here's..." atau langsung JSON
    # Coba extract JSON block
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not json_match:
        raise ValueError(f"No JSON found in response: {response_text[:100]}")

    json_text = json_match.group(0)
    parsed = json.loads(json_text)

    # Cleanup dan validasi
    hashtags = _normalize_hashtags(parsed.get("hashtags", []))
    defaults = _default_metadata(language)
    return {
        "title": str(parsed.get("title", defaults["title"]))[:50],
        "caption": str(parsed.get("caption", ""))[:200],
        "hashtags": hashtags,
    }


def _normalize_language(language: str) -> str:
    return "en" if language == "en" else "id"


def _default_metadata(language: str) -> dict:
    if _normalize_language(language) == "en":
        return {
            "title": "Interesting Video",
            "caption": "Watch and enjoy this clip.",
            "hashtags": ["content", "video"],
        }
    return {
        "title": "Video Menarik",
        "caption": "Tonton dan nikmati konten ini.",
        "hashtags": ["content", "viral"],
    }


def _normalize_hashtags(value) -> list[str]:
    """Accept list/string hashtag output and normalize to plain tag names."""
    if isinstance(value, str):
        raw_tags = re.split(r"[\s,]+", value)
    elif isinstance(value, list):
        raw_tags = value
    else:
        raw_tags = []

    tags = []
    for tag in raw_tags:
        cleaned = str(tag).replace("#", "").strip()
        if cleaned:
            tags.append(cleaned)
    return tags[:7]


def test_ollama_connection() -> bool:
    """Test apakah Ollama server bisa diakses."""
    try:
        response = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Ollama connection failed: {e}")
        return False
