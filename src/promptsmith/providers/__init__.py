from __future__ import annotations

import os

from promptsmith.models.types import Provider
from promptsmith.providers.anthropic import AnthropicProvider
from promptsmith.providers.base import BaseProvider
from promptsmith.providers.mock import MockProvider
from promptsmith.providers.openai import OpenAIProvider

PROVIDER_MAP: dict[Provider, type[BaseProvider]] = {
    Provider.OPENAI: OpenAIProvider,
    Provider.ANTHROPIC: AnthropicProvider,
    Provider.MOCK: MockProvider,
}


def get_provider(
    provider: Provider | str,
    model: str | None = None,
    api_key: str | None = None,
) -> BaseProvider:
    """Factory to create a provider instance."""
    if isinstance(provider, str):
        provider = Provider(provider)

    provider_cls = PROVIDER_MAP[provider]

    if model is None:
        model = DEFAULT_MODELS.get(provider, "mock")

    return provider_cls(model=model, api_key=api_key)


DEFAULT_MODELS: dict[Provider, str] = {
    Provider.OPENAI: "gpt-4o-mini",
    Provider.ANTHROPIC: "claude-3-5-sonnet-20241022",
    Provider.MOCK: "mock",
}

__all__ = [
    "BaseProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "MockProvider",
    "get_provider",
    "PROVIDER_MAP",
]
