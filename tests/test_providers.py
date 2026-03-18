import json
from types import SimpleNamespace

import httpx
import pytest

from mailagent.providers import ProviderError
from mailagent.providers.anthropic import AnthropicProvider
from mailagent.providers.gemini import GeminiProvider
from mailagent.providers.groq import GroqProvider
from mailagent.providers.openai import OpenAIProvider
from mailagent.providers.openrouter import OpenRouterProvider


def _make_response(status: int, payload: dict | str) -> SimpleNamespace:
    if isinstance(payload, str):
        text = payload

        def json_loader():
            return json.loads(payload)
    else:
        text = json.dumps(payload)

        def json_loader():
            return payload

    return SimpleNamespace(status_code=status, text=text, json=json_loader)


def test_openai_parses_response(monkeypatch):
    provider = OpenAIProvider(model="gpt-4o", api_key="k")

    calls = []

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            calls.append((url, headers, json))
            return _make_response(
                200,
                {
                    "choices": [
                        {"message": {"content": "hello"}},
                    ],
                    "usage": {"total_tokens": 10},
                },
            )

    monkeypatch.setattr(httpx, "Client", FakeClient)
    out = provider.complete("sys", "user")

    assert out.text == "hello"
    assert out.usage == {"total_tokens": 10}
    assert calls[0][0].endswith("/chat/completions")


def test_retry_on_5xx_then_success(monkeypatch):
    provider = GroqProvider(model="llama", api_key="k", retries=1)

    responses = [
        _make_response(500, {"error": "server"}),
        _make_response(200, {"choices": [{"message": {"content": "ok"}}]}),
    ]

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            return responses.pop(0)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("time.sleep", lambda _: None)

    out = provider.complete("sys", "user")
    assert out.text == "ok"


def test_timeout_raises_provider_error(monkeypatch):
    provider = OpenRouterProvider(model="m", api_key="k", retries=1)

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("time.sleep", lambda _: None)

    with pytest.raises(ProviderError):
        provider.complete("sys", "user")


def test_anthropic_response_parsing(monkeypatch):
    provider = AnthropicProvider(model="claude", api_key="k")

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            return _make_response(200, {"content": [{"text": "anthropic ok"}]})

    monkeypatch.setattr(httpx, "Client", FakeClient)
    out = provider.complete("sys", "user")
    assert out.text == "anthropic ok"


def test_gemini_response_parsing(monkeypatch):
    provider = GeminiProvider(model="gemini-2.0-flash", api_key="k")

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            return _make_response(
                200,
                {
                    "candidates": [{"content": {"parts": [{"text": "gemini ok"}]}}],
                    "usageMetadata": {"totalTokenCount": 42},
                },
            )

    monkeypatch.setattr(httpx, "Client", FakeClient)
    out = provider.complete("sys", "user")
    assert out.text == "gemini ok"
    assert out.usage == {"totalTokenCount": 42}
