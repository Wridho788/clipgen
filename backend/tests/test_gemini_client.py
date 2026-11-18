import pytest

from app.core.pipeline import gemini_client
from app.core.pipeline.gemini_client import GeminiError, generate_text


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _payload(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_parse_model_chain_falls_back_to_default_when_empty():
    assert gemini_client._parse_model_chain(None) == list(gemini_client.DEFAULT_MODEL_CHAIN)
    assert gemini_client._parse_model_chain("  ") == list(gemini_client.DEFAULT_MODEL_CHAIN)


def test_parse_model_chain_keeps_order_and_drops_blanks():
    chain = gemini_client._parse_model_chain("gemini-a, ,gemini-b,")
    assert chain == ["gemini-a", "gemini-b"]


def test_generate_text_returns_first_model_that_answers(monkeypatch):
    captured = []

    def fake_post(url, headers, json, timeout):
        captured.append(url)
        return FakeResponse(200, _payload('{"title":"A"}'))

    monkeypatch.setattr(gemini_client.requests, "post", fake_post)

    result = generate_text(
        "prompt",
        api_key="key",
        model_chain="gemini-a,gemini-b",
    )

    assert result.text == '{"title":"A"}'
    assert result.model == "gemini-a"
    assert result.attempts == 1
    assert len(captured) == 1
    assert "gemini-a:generateContent" in captured[0]


def test_generate_text_falls_back_to_next_model_on_503(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        if "gemini-a" in url:
            return FakeResponse(503, text="high demand")
        return FakeResponse(200, _payload('{"title":"B"}'))

    monkeypatch.setattr(gemini_client.requests, "post", fake_post)

    result = generate_text(
        "prompt",
        api_key="key",
        model_chain="gemini-a,gemini-b",
        max_attempts_per_model=1,
    )

    assert result.text == '{"title":"B"}'
    assert result.model == "gemini-b"
    assert len(calls) == 2


def test_generate_text_retries_a_model_before_moving_on(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(429, text="quota exceeded")
        return FakeResponse(200, _payload('{"title":"C"}'))

    monkeypatch.setattr(gemini_client.requests, "post", fake_post)
    monkeypatch.setattr(gemini_client.time, "sleep", lambda seconds: None)

    result = generate_text(
        "prompt",
        api_key="key",
        model_chain="gemini-a",
        max_attempts_per_model=2,
    )

    assert result.text == '{"title":"C"}'
    assert result.model == "gemini-a"
    assert len(calls) == 2


def test_generate_text_does_not_retry_a_404(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        return FakeResponse(404, text="model not found")

    monkeypatch.setattr(gemini_client.requests, "post", fake_post)

    with pytest.raises(GeminiError):
        generate_text(
            "prompt",
            api_key="key",
            model_chain="gemini-a,gemini-b",
            max_attempts_per_model=3,
        )

    # A 404 means the model is gone for this key, so it is tried once only.
    assert len(calls) == 2


def test_generate_text_requires_an_api_key():
    with pytest.raises(GeminiError):
        generate_text("prompt", api_key="")


def test_generate_text_raises_when_every_model_fails(monkeypatch):
    monkeypatch.setattr(
        gemini_client.requests,
        "post",
        lambda *a, **k: FakeResponse(503, text="busy"),
    )

    with pytest.raises(GeminiError) as error:
        generate_text(
            "prompt",
            api_key="key",
            model_chain="gemini-a,gemini-b",
            max_attempts_per_model=1,
        )

    assert "gemini-a" in str(error.value)
    assert "gemini-b" in str(error.value)


def test_generate_text_sends_the_key_in_a_header_not_the_url(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResponse(200, _payload("{}"))

    monkeypatch.setattr(gemini_client.requests, "post", fake_post)

    generate_text("prompt", api_key="secret-key", model_chain="gemini-a")

    assert "secret-key" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "secret-key"


def test_generate_text_requests_json_mode(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return FakeResponse(200, _payload("{}"))

    monkeypatch.setattr(gemini_client.requests, "post", fake_post)

    generate_text("prompt", api_key="key", model_chain="gemini-a", json_mode=True)

    assert captured["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_check_connection_reports_failure_without_a_key():
    assert gemini_client.check_connection("") is False


def test_check_connection_uses_the_model_endpoint(monkeypatch):
    captured = {}

    def fake_get(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResponse(200)

    monkeypatch.setattr(gemini_client.requests, "get", fake_get)

    assert gemini_client.check_connection("key") is True
    # The model endpoint validates the key without spending generation quota.
    assert "generateContent" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "key"


def test_check_connection_reports_a_rejected_key(monkeypatch):
    monkeypatch.setattr(
        gemini_client.requests,
        "get",
        lambda *a, **k: FakeResponse(400),
    )

    assert gemini_client.check_connection("key") is False
