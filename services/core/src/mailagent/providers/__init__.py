from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict[str, Any] | None = None


class ProviderError(Exception):
    """Raised when a provider call fails after retries."""


class BaseProvider(ABC):
    """Base class for LLM provider adapters."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str | None = None,
        timeout: int = 30,
        retries: int = 1,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries

    @abstractmethod
    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 500
    ) -> LLMResponse:
        """Send a chat completion request. Must handle retries internally."""

    def classify(self, system_prompt: str, user_prompt: str) -> str:
        response = self.complete(system_prompt, user_prompt, max_tokens=50)
        return response.text.strip()

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.complete(system_prompt, user_prompt, max_tokens=1000)
        return response.text.strip()

    def _post_json_with_retries(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=float(self.timeout)) as client:
                    response = client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(2)
                    continue
                raise ProviderError(
                    f"Provider timeout after {self.retries + 1} attempts"
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(f"Provider HTTP error: {exc}") from exc

            status = response.status_code

            if status >= 500:
                if attempt < self.retries:
                    time.sleep(2)
                    continue
                body = response.text[:1000]
                raise ProviderError(f"Provider server error {status}: {body}")

            if status >= 400:
                body = response.text[:1000]
                raise ProviderError(f"Provider request failed {status}: {body}")

            try:
                return response.json()
            except ValueError as exc:
                last_error = exc
                raise ProviderError(
                    f"Provider returned invalid JSON: {response.text[:1000]}"
                ) from exc

        raise ProviderError(f"Provider returned invalid JSON: {last_error}")

    def _openai_compatible_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        default_base_url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> LLMResponse:
        base = (self.base_url or default_base_url).rstrip("/")
        url = f"{base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }

        data = self._post_json_with_retries(url=url, headers=headers, payload=payload)

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"Unexpected provider response payload: {data}"
            ) from exc

        return LLMResponse(text=str(text), model=self.model, usage=data.get("usage"))


PROVIDERS: dict[str, type[BaseProvider]] = {}


def register_provider(name: str) -> Callable[[type[BaseProvider]], type[BaseProvider]]:
    """Decorator to register a provider class."""

    def decorator(cls: type[BaseProvider]) -> type[BaseProvider]:
        PROVIDERS[name] = cls
        return cls

    return decorator


_BUILTINS_LOADED = False


def _ensure_builtins() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return

    from . import anthropic, gemini, groq, openai, openrouter  # noqa: F401

    _BUILTINS_LOADED = True


def get_provider(name: str, **kwargs: Any) -> BaseProvider:
    """Instantiate a provider by type name."""
    _ensure_builtins()
    if name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider type: {name}. Available: {list(PROVIDERS.keys())}"
        )
    return PROVIDERS[name](**kwargs)
