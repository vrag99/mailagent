from . import BaseProvider, LLMResponse, register_provider


@register_provider("openrouter")
class OpenRouterProvider(BaseProvider):
    """OpenRouter adapter using OpenAI-compatible chat completions."""

    def __init__(
        self,
        *args,
        http_referer: str | None = None,
        x_title: str | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.http_referer = http_referer
        self.x_title = x_title

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 500
    ) -> LLMResponse:
        headers: dict[str, str] = {}
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.x_title:
            headers["X-Title"] = self.x_title

        return self._openai_compatible_complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            default_base_url="https://openrouter.ai/api/v1",
            extra_headers=headers,
        )
