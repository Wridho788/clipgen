import pytest

from app.core.pipeline import gemini_client
from app.core.pipeline import metadata_gen
from app.core.pipeline.metadata_gen import _normalize_hashtags, _parse_response
from app.schemas import CampaignBrief


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (["#funny", "viral", " clip "], ["funny", "viral", "clip"]),
        ("#funny, viral clip", ["funny", "viral", "clip"]),
        (None, []),
    ],
)
def test_normalize_hashtags(value, expected):
    assert _normalize_hashtags(value) == expected


def test_parse_response_accepts_hashtag_string():
    parsed = _parse_response(
        '{"title":"Moment Besar","caption":"Caption pendek","hashtags":"#funny viral"}'
    )

    assert parsed["title"] == "Moment Besar"
    assert parsed["hashtags"] == ["funny", "viral"]


def test_call_ollama_uses_configurable_timeout_and_json_mode(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"response": '{"title":"A","caption":"B","hashtags":[]}'}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(metadata_gen.requests, "post", fake_post)
    monkeypatch.setattr(metadata_gen.settings, "ollama_base_url", "http://ollama.test")
    monkeypatch.setattr(metadata_gen.settings, "ollama_model", "test-model")
    monkeypatch.setattr(metadata_gen.settings, "ollama_timeout_seconds", 7)
    monkeypatch.setattr(metadata_gen.settings, "ollama_num_predict", 123)

    response = metadata_gen._call_ollama("transcript with enough useful words")

    assert response == '{"title":"A","caption":"B","hashtags":[]}'
    assert captured["url"] == "http://ollama.test/api/generate"
    assert captured["timeout"] == 7
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["format"] == "json"
    assert captured["json"]["options"]["num_predict"] == 123


def test_english_prompt_and_default_metadata(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"response": '{"title":"A","caption":"B","hashtags":[]}' }

    def fake_post(url, json, timeout):
        captured["prompt"] = json["prompt"]
        return FakeResponse()

    monkeypatch.setattr(metadata_gen.requests, "post", fake_post)

    metadata_gen._call_ollama("a useful transcript", "en")

    assert "in English" in captured["prompt"]
    assert metadata_gen.generate_metadata("short", "en")["title"] == "Interesting Video"


def test_campaign_brief_adds_required_metadata_constraints(monkeypatch):
    brief = CampaignBrief(id="yava", name="YAVA", hashtags=["YAVA"], cta="Klik keranjang kuning")
    monkeypatch.setattr(metadata_gen, "_call_ollama", lambda *args, **kwargs: '{"title":"A","caption":"Caption","hashtags":[]}')
    metadata = metadata_gen.generate_metadata("Transcript yang cukup panjang untuk diuji", campaign_brief=brief)

    assert "YAVA" in metadata["hashtags"]
    assert "Klik keranjang kuning" in metadata["caption"]


def test_generate_metadata_uses_gemini_when_the_provider_is_configured(monkeypatch):
    """The provider setting decides which backend runs."""
    called = {}

    def fake_gemini(transcript_text, language="id", campaign_brief=None):
        called["gemini"] = True
        return '{"title":"Dari Gemini","caption":"Caption","hashtags":[]}'

    def fake_ollama(*args, **kwargs):
        called["ollama"] = True
        return '{"title":"Dari Ollama","caption":"Caption","hashtags":[]}'

    monkeypatch.setattr(metadata_gen.settings, "metadata_provider", "gemini")
    monkeypatch.setattr(metadata_gen, "_call_gemini", fake_gemini)
    monkeypatch.setattr(metadata_gen, "_call_ollama", fake_ollama)

    metadata = metadata_gen.generate_metadata("Transkrip yang cukup panjang untuk diuji")

    assert metadata["title"] == "Dari Gemini"
    assert called.get("gemini") is True
    assert "ollama" not in called


def test_call_gemini_passes_the_campaign_brief_to_the_prompt(monkeypatch):
    """The brief must reach the model, not just be applied afterwards."""
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return gemini_client.GeminiResult(text='{"title":"A","caption":"B","hashtags":[]}', model="m", attempts=1)

    brief = CampaignBrief(id="yava", name="YAVA", hashtags=["YAVA"], cta="Klik keranjang kuning")

    monkeypatch.setattr(metadata_gen.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(metadata_gen.gemini_client, "generate_text", fake_generate)

    result = metadata_gen._call_gemini("Transkrip yang cukup panjang", "id", brief)

    assert result == '{"title":"A","caption":"B","hashtags":[]}'
    assert "YAVA" in captured["prompt"]
    assert "Klik keranjang kuning" in captured["prompt"]
    assert captured["kwargs"]["api_key"] == "test-key"


def test_call_gemini_requires_a_key(monkeypatch):
    monkeypatch.setattr(metadata_gen.settings, "gemini_api_key", None)

    with pytest.raises(RuntimeError):
        metadata_gen._call_gemini("Transkrip yang cukup panjang")


def test_call_gemini_asks_for_json_and_an_indonesian_prompt(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return gemini_client.GeminiResult(text="{}", model="m", attempts=1)

    monkeypatch.setattr(metadata_gen.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(metadata_gen.gemini_client, "generate_text", fake_generate)

    metadata_gen._call_gemini("Transkrip yang cukup panjang", "id")

    assert "Bahasa Indonesia" in captured["prompt"]
    assert captured["kwargs"]["json_mode"] is True
