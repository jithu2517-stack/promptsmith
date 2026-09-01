from __future__ import annotations

from promptsmith.models.types import Provider
from promptsmith.providers import get_provider
from promptsmith.providers.anthropic import AnthropicProvider
from promptsmith.providers.openai import OpenAIProvider


class TestProviderFactory:
    def test_get_mock_provider(self):
        provider = get_provider("mock")
        assert provider.provider == Provider.MOCK

    def test_get_openai_provider(self):
        provider = get_provider("openai", model="gpt-4o-mini")
        assert provider.provider == Provider.OPENAI
        assert provider.model == "gpt-4o-mini"

    def test_get_anthropic_provider(self):
        provider = get_provider("anthropic", model="claude-3-haiku-20240307")
        assert provider.provider == Provider.ANTHROPIC
        assert provider.model == "claude-3-haiku-20240307"

    def test_get_provider_with_enum(self):
        provider = get_provider(Provider.MOCK)
        assert provider.provider == Provider.MOCK


class TestOpenAIProvider:
    def test_estimate_cost(self):
        provider = OpenAIProvider(model="gpt-4o-mini")
        cost = provider.estimate_cost(1000, 500)
        assert cost > 0
        assert cost < 0.01

    def test_unknown_model_cost_zero(self):
        provider = OpenAIProvider(model="unknown-model")
        assert provider.estimate_cost(1000, 500) == 0.0


class TestAnthropicProvider:
    def test_estimate_cost(self):
        provider = AnthropicProvider(model="claude-3-haiku-20240307")
        cost = provider.estimate_cost(1000, 500)
        assert cost > 0
        assert cost < 0.01

    def test_unknown_model_cost_zero(self):
        provider = AnthropicProvider(model="unknown-model")
        assert provider.estimate_cost(1000, 500) == 0.0
