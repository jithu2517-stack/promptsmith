from __future__ import annotations

from abc import ABC, abstractmethod

from promptsmith.models.types import Message, Provider, RunResult


class BaseProvider(ABC):
    """Abstract base for AI model providers."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key

    @property
    @abstractmethod
    def provider(self) -> Provider:
        ...

    @abstractmethod
    async def run(
        self,
        messages: list[Message],
        **kwargs: object,
    ) -> RunResult:
        ...

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        ...
