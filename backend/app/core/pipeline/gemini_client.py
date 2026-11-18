"""
Shared Gemini (Google AI Studio) client.

The free tier is not a single, always-available model: each model has its own
per-minute quota bucket, popular models answer ``503 UNAVAILABLE`` while they
are under load, and a bucket that runs dry answers ``429`` without sending a
``Retry-After`` header.  A single hard-coded model therefore fails often
enough to be noticed.

This client encodes what actually works against that behaviour:

* **A fallback chain.**  Models are tried in order.  The quota buckets are
  per-model, so moving to the next model is a real second chance rather than
  the same exhausted bucket again.
* **Retry with backoff.**  ``429`` and ``503`` are retried on the same model
  before the chain advances, because both are usually transient.
* **The key stays in a header.**  It is never written into a URL, a log line,
  or an error message.

Used by the ClipGen metadata pipeline and by the standalone Hook Lab chatbot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from loguru import logger

# Status codes worth retrying: the bucket is empty (429) or the model is busy
# (503).  A 404 means the model is gone for this key, so it is not retried.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Default chain.  The first entry is the strongest model that stays available
# on the free tier; the later entries are progressively cheaper and have
# proven to stay available when the first ones are saturated or busy.
DEFAULT_MODEL_CHAIN: tuple[str, ...] = (
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiError(RuntimeError):
    """Every model in the chain failed."""


@dataclass(frozen=True)
class GeminiResult:
    """One successful generation."""

    text: str
    model: str
    attempts: int


def _parse_model_chain(chain: str | None) -> list[str]:
    """Turn a comma-separated model list into an ordered chain.

    An empty value falls back to :data:`DEFAULT_MODEL_CHAIN` so a missing
    setting never silently disables generation.
    """
    models = [part.strip() for part in (chain or "").split(",") if part.strip()]
    return models or list(DEFAULT_MODEL_CHAIN)


def _extract_text(payload: dict) -> str:
    """Pull the text parts out of a ``generateContent`` response."""
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    return "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ).strip()


def generate_text(
    prompt: str,
    *,
    api_key: str,
    model_chain: str | None = None,
    timeout_seconds: int = 30,
    max_attempts_per_model: int = 2,
    backoff_seconds: float = 1.5,
    json_mode: bool = True,
) -> GeminiResult:
    """Generate text with Gemini, trying each model in the chain in turn.

    Args:
        prompt: The full prompt text.
        api_key: Google AI Studio key. Sent as a header, never in the URL.
        model_chain: Comma-separated models, tried in order.
        timeout_seconds: Per-request timeout.
        max_attempts_per_model: Attempts on one model before moving on.
        backoff_seconds: Base delay for the exponential backoff between
            attempts.  The free tier sends no ``Retry-After``, so the delay
            is ours to choose.
        json_mode: Ask the API for a JSON object response.

    Raises:
        GeminiError: Every model in the chain failed.
    """
    if not api_key:
        raise GeminiError("GEMINI_API_KEY belum dikonfigurasi")

    models = _parse_model_chain(model_chain)
    errors: list[str] = []
    attempts = 0

    for model in models:
        for attempt in range(1, max_attempts_per_model + 1):
            attempts += 1
            url = f"{_API_ROOT}/{model}:generateContent"
            payload: dict = {"contents": [{"parts": [{"text": prompt}]}]}
            if json_mode:
                payload["generationConfig"] = {"responseMimeType": "application/json"}

            try:
                response = requests.post(
                    url,
                    headers={"x-goog-api-key": api_key},
                    json=payload,
                    timeout=timeout_seconds,
                )
            except requests.RequestException as error:
                errors.append(f"{model}: {type(error).__name__}")
                break  # A connection failure is not fixed by retrying the same host.

            if response.status_code == 200:
                text = _extract_text(response.json())
                if text:
                    logger.info(f"Gemini {model} answered on attempt {attempt}")
                    return GeminiResult(text=text, model=model, attempts=attempts)
                errors.append(f"{model}: empty response")
                break

            detail = response.text[:200]
            errors.append(f"{model}: HTTP {response.status_code} {detail}")

            if response.status_code not in _RETRYABLE_STATUS:
                # 404 and 4xx mean this model is unusable for this key.
                break

            if attempt < max_attempts_per_model:
                delay = backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    f"Gemini {model} HTTP {response.status_code}; "
                    f"retrying in {delay:.1f}s ({attempt}/{max_attempts_per_model})"
                )
                time.sleep(delay)

        logger.warning(f"Gemini model {model} exhausted; trying the next model")

    raise GeminiError("; ".join(errors))


def check_connection(api_key: str, model: str = "gemini-3.8-flash") -> bool:
    """Check the key without spending generation quota.

    The model endpoint validates the key and answers ``200`` for a model the
    key may call, without consuming a generateContent request.
    """
    if not api_key:
        return False
    try:
        response = requests.get(
            f"{_API_ROOT}/{model}",
            headers={"x-goog-api-key": api_key},
            timeout=10,
        )
    except requests.RequestException as error:
        logger.error(f"Gemini connection failed: {type(error).__name__}")
        return False
    return response.status_code == 200
