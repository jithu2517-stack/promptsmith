from __future__ import annotations

import os
import time

from promptsmith.models.types import Message, Provider, RunResult
from promptsmith.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI models (GPT-4, GPT-3.5, etc.)."""

    PRICING: dict[str, tuple[float, float]] = {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-4": (30.00, 60.00),
        "gpt-3.5-turbo": (0.50, 1.50),
    }

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None) -> None:
        super().__init__(model, api_key)
        self._client = None

    @property
    def provider(self) -> Provider:
        return Provider.OPENAI

    def _get_client(self) -> object:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install promptsmith[openai]"
                )
            key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
            self._client = AsyncOpenAI(api_key=key)
        return self._client

    async def run(
        self,
        messages: list[Message],
        **kwargs: object,
    ) -> RunResult:
        client = self._get_client()
        start = time.monotonic()

        fmt_messages = [
            {"role": m.role.value, "content": m.content} for m in messages
        ]

        response = await client.chat.completions.create(
            model=self.model,
            messages=fmt_messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 1024),
        )

        latency_ms = (time.monotonic() - start) * 1000
        choice = response.choices[0]
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return RunResult(
            prompt_name="",
            prompt_version=0,
            prompt_hash="",
            provider=Provider.OPENAI,
            model=self.model,
            messages_sent=list(messages),
            response_text=choice.message.content or "",
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
            cost_usd=self.estimate_cost(input_tokens, output_tokens),
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_price, output_price = self.PRICING.get(
            self.model, (0.0, 0.0)
        )
        return (
            (input_tokens / 1_000_000) * input_price
            + (output_tokens / 1_000_000) * output_price
        )

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            return max(1, len(text) // 4)
