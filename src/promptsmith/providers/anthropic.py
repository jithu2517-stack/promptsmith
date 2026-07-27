from __future__ import annotations

import os
import time

from promptsmith.models.types import Message, Provider, RunResult
from promptsmith.providers.base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic models (Claude)."""

    PRICING: dict[str, tuple[float, float]] = {
        "claude-3-5-sonnet-20241022": (3.00, 15.00),
        "claude-3-opus-20240229": (15.00, 75.00),
        "claude-3-sonnet-20240229": (3.00, 15.00),
        "claude-3-haiku-20240307": (0.25, 1.25),
    }

    def __init__(
        self, model: str = "claude-3-5-sonnet-20241022", api_key: str | None = None
    ) -> None:
        super().__init__(model, api_key)
        self._client = None

    @property
    def provider(self) -> Provider:
        return Provider.ANTHROPIC

    def _get_client(self) -> object:
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install promptsmith[anthropic]"
                )
            key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            self._client = AsyncAnthropic(api_key=key)
        return self._client

    async def run(
        self,
        messages: list[Message],
        **kwargs: object,
    ) -> RunResult:
        client = self._get_client()
        start = time.monotonic()

        system_messages = [m for m in messages if m.role == "system"]
        chat_messages = [m for m in messages if m.role != "system"]

        system_text = "\n".join(m.content for m in system_messages) if system_messages else None
        fmt_messages = [
            {"role": m.role.value, "content": m.content} for m in chat_messages
        ]

        kwargs_dict: dict[str, object] = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": fmt_messages,
        }
        if system_text:
            kwargs_dict["system"] = system_text

        response = await client.messages.create(**kwargs_dict)

        latency_ms = (time.monotonic() - start) * 1000
        response_text = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0

        return RunResult(
            prompt_name="",
            prompt_version=0,
            prompt_hash="",
            provider=Provider.ANTHROPIC,
            model=self.model,
            messages_sent=list(messages),
            response_text=response_text,
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
        return max(1, len(text) // 4)
