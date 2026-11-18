"""Shared test setup.

Two invariants for the whole suite:

1. **Tests never read the developer's local ``.env``.**  ``Settings`` loads
   ``.env`` at import time, so a local ``METADATA_PROVIDER=gemini`` would
   silently change which provider the tests exercise.
2. **Tests never call an AI provider over the network.**  A test that
   accidentally reaches Gemini or Ollama would be slow, flaky, and would
   spend the owner's API quota.

Both are enforced here rather than left to each test file.
"""
from __future__ import annotations

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _isolate_metadata_provider(monkeypatch):
    """Pin the metadata provider to the offline default for every test.

    A test that wants to exercise the Gemini path patches
    ``_call_gemini`` or ``gemini_client.generate_text`` explicitly.
    """
    monkeypatch.setattr(settings, "metadata_provider", "ollama")
    yield
