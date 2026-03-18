from . import BaseProvider, LLMResponse, register_provider


@register_provider("openai")
class OpenAIProvider(BaseProvider):
    """Covers OpenAI API and OpenAI-compatible endpoints."""

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 500
    ) -> LLMResponse:
        return self._openai_compatible_complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            default_base_url="https://api.openai.com/v1",
        )
