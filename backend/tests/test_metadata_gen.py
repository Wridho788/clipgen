import pytest

from app.core.pipeline import metadata_gen
from app.core.pipeline.metadata_gen import _normalize_hashtags, _parse_response


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
