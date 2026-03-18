from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from . import BaseProvider, LLMResponse, ProviderError, register_provider


@register_provider("gemini")
class GeminiProvider(BaseProvider):
    """Google Gemini generateContent adapter."""

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 500
    ) -> LLMResponse:
        if self.base_url:
            url = self.base_url
        else:
            model = quote_plus(self.model)
            url = (
                "https://generativelanguage.googleapis.com/"
                f"v1beta/models/{model}:generateContent?key={self.api_key}"
            )

        headers = {"Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }

        data = self._post_json_with_retries(url=url, headers=headers, payload=payload)

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"Unexpected provider response payload: {data}"
            ) from exc

        usage = data.get("usageMetadata")
        return LLMResponse(text=str(text), model=self.model, usage=usage)
