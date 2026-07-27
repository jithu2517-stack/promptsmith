from __future__ import annotations

import asyncio
import os
import time

from promptsmith.models.types import Message, Provider, RunResult
from promptsmith.providers.base import BaseProvider


class MockProvider(BaseProvider):
    """Mock provider for testing without API keys. Returns deterministic responses."""

    def __init__(self, model: str = "mock", api_key: str | None = None) -> None:
        super().__init__(model, api_key)
        self._counter = 0

    @property
    def provider(self) -> Provider:
        return Provider.MOCK

    async def run(
        self,
        messages: list[Message],
        **kwargs: object,
    ) -> RunResult:
        self._counter += 1
        start = time.monotonic()

        await asyncio.sleep(0.05)

        user_content = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )

        response = (
            f'[MOCK RESPONSE #{self._counter}] Received prompt: "{user_content[:100]}"\n'
            f"This is a deterministic mock response for testing purposes. "
            f"Model: {self.model}, Messages: {len(messages)}"
        )

        input_text = " ".join(m.content for m in messages)
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(response)
        latency_ms = (time.monotonic() - start) * 1000

        return RunResult(
            prompt_name="mock",
            prompt_version=0,
            prompt_hash="mock",
            provider=Provider.MOCK,
            model=self.model,
            messages_sent=list(messages),
            response_text=response,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
