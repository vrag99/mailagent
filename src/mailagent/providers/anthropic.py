from typing import Any

from . import BaseProvider, LLMResponse, ProviderError, register_provider


@register_provider("anthropic")
class AnthropicProvider(BaseProvider):
    """Anthropic Messages API adapter."""

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 500
    ) -> LLMResponse:
        url = self.base_url or "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": max_tokens,
        }
        data = self._post_json_with_retries(url=url, headers=headers, payload=payload)

        try:
            text = data["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"Unexpected provider response payload: {data}"
            ) from exc

        return LLMResponse(text=str(text), model=self.model, usage=data.get("usage"))
