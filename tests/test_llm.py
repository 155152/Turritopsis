from __future__ import annotations

import json

import httpx
import pytest

from turritopsis.config import LLMConfig
from turritopsis.llm import LLMClient


SCHEMA = {
    "type": "object", "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"], "additionalProperties": False,
}


@pytest.mark.parametrize("provider", ["openai", "anthropic", "openai-compatible"])
def test_provider_adapters_send_supported_shape_and_parse_json(provider, monkeypatch):
    monkeypatch.setenv("FAKE_LLM_KEY", "secret-value")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        if provider == "openai":
            return httpx.Response(200, json={"output": [{"type": "message", "content": [
                {"type": "output_text", "text": '{"ok":true}'},
            ]}]})
        if provider == "anthropic":
            return httpx.Response(200, json={"content": [{"type": "text", "text": '{"ok":true}'}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})

    base = "https://api.example.test/v1"
    config = LLMConfig(provider, "test-model", "FAKE_LLM_KEY", base)
    result = LLMClient(config, httpx.MockTransport(handler)).complete_json("system", "prompt", SCHEMA, "test")
    assert result == {"ok": True}
    assert captured["body"]["model"] == "test-model"
    if provider == "openai":
        assert captured["url"].endswith("/responses")
        assert captured["body"]["text"]["format"]["strict"] is True
        assert captured["body"]["store"] is False
    elif provider == "anthropic":
        assert captured["url"].endswith("/messages")
        assert captured["headers"]["anthropic-version"] == "2023-06-01"
    else:
        assert captured["url"].endswith("/chat/completions")
        assert captured["body"]["response_format"] == {"type": "json_object"}


def test_compatible_provider_retries_without_response_format(monkeypatch):
    monkeypatch.setenv("FAKE_LLM_KEY", "secret-value")
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if "response_format" in body:
            return httpx.Response(400, text="response_format unsupported")
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})

    config = LLMConfig("openai-compatible", "local-model", "FAKE_LLM_KEY", "https://local.test/v1")
    result = LLMClient(config, httpx.MockTransport(handler)).complete_json("system", "prompt", SCHEMA, "test")
    assert result == {"ok": True}
    assert len(requests) == 2 and "response_format" not in requests[1]
