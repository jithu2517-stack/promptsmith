from __future__ import annotations

import asyncio
import tempfile

import pytest

from promptsmith.core.evaluator import evaluate_test_case
from promptsmith.core.runner import Runner
from promptsmith.core.vault import Vault
from promptsmith.models.types import (
    Message,
    Prompt,
    Provider,
    Role,
    RunResult,
    TestCase,
)


class TestEvaluator:
    def test_passes_all_checks(self):
        tc = TestCase(
            name="pass-test",
            expected_patterns=["hello"],
            forbidden_patterns=["error"],
            min_tokens=5,
            max_tokens=100,
        )
        result = RunResult(
            prompt_name="t",
            prompt_version=1,
            prompt_hash="h",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="hello world, this is a test",
            tokens_input=10,
            tokens_output=15,
            latency_ms=50,
            cost_usd=0,
        )
        tr = evaluate_test_case(tc, result)
        assert tr.passed is True
        assert len(tr.checks) == 4
        assert all(c["passed"] for c in tr.checks)

    def test_fails_expected_pattern(self):
        tc = TestCase(name="fail-expected", expected_patterns=["MISSING_TEXT"])
        result = RunResult(
            prompt_name="t",
            prompt_version=1,
            prompt_hash="h",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="something else entirely",
            tokens_input=1,
            tokens_output=10,
            latency_ms=1,
            cost_usd=0,
        )
        tr = evaluate_test_case(tc, result)
        assert tr.passed is False

    def test_fails_forbidden_pattern(self):
        tc = TestCase(name="fail-forbidden", forbidden_patterns=["secret"])
        result = RunResult(
            prompt_name="t",
            prompt_version=1,
            prompt_hash="h",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="this contains secret information",
            tokens_input=1,
            tokens_output=10,
            latency_ms=1,
            cost_usd=0,
        )
        tr = evaluate_test_case(tc, result)
        assert tr.passed is False

    def test_fails_min_tokens(self):
        tc = TestCase(name="fail-min", min_tokens=100)
        result = RunResult(
            prompt_name="t",
            prompt_version=1,
            prompt_hash="h",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="short",
            tokens_input=1,
            tokens_output=10,
            latency_ms=1,
            cost_usd=0,
        )
        tr = evaluate_test_case(tc, result)
        assert tr.passed is False

    def test_fails_on_error(self):
        tc = TestCase(name="err-test")
        result = RunResult(
            prompt_name="t",
            prompt_version=1,
            prompt_hash="h",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="",
            tokens_input=0,
            tokens_output=0,
            latency_ms=0,
            cost_usd=0,
            error="API error",
        )
        tr = evaluate_test_case(tc, result)
        assert tr.passed is False
        assert tr.error == "API error"


class TestRunner:
    @pytest.fixture
    def setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(tmp)
            vault.init()

            prompt = Prompt(
                name="greeting",
                messages=[
                    Message(Role.SYSTEM, "You are a helpful assistant."),
                    Message(Role.USER, "Say hello to {{name}}"),
                ],
            )
            vault.save_prompt(prompt)

            tc = TestCase(
                name="greeting-test",
                expected_patterns=["hello", "mock"],
                forbidden_patterns=["error"],
            )
            vault.save_test(tc)

            yield vault

    def test_run_prompt_mock(self, setup):
        runner = Runner(setup)
        prompt = setup.get_prompt("greeting")
        result = asyncio.run(
            runner.run_prompt(prompt, provider=Provider.MOCK)
        )
        assert result.response_text
        assert "MOCK RESPONSE" in result.response_text
        assert result.provider == Provider.MOCK
        assert result.tokens_input > 0

    def test_run_with_variables(self, setup):
        runner = Runner(setup)
        prompt = setup.get_prompt("greeting")
        result = asyncio.run(
            runner.run_prompt(
                prompt,
                provider=Provider.MOCK,
                variables={"name": "World"},
            )
        )
        assert result.response_text

    def test_run_test_single(self, setup):
        runner = Runner(setup)
        result = asyncio.run(
            runner.run_test(
                prompt_name="greeting",
                test_name="greeting-test",
                provider=Provider.MOCK,
            )
        )
        assert result.test_name == "greeting-test"
        assert result.passed is True

    def test_run_test_suite(self, setup):
        runner = Runner(setup)
        results = asyncio.run(
            runner.run_test_suite("greeting", provider=Provider.MOCK)
        )
        assert len(results) == 1
        assert results[0].passed is True

    def test_cache_usage(self, setup):
        from promptsmith.core.cache import Cache

        with tempfile.TemporaryDirectory() as tmp:
            cache = Cache(f"{tmp}/cache.db")
            runner = Runner(setup, cache=cache)
            prompt = setup.get_prompt("greeting")

            result1 = asyncio.run(
                runner.run_prompt(prompt, provider=Provider.MOCK)
            )
            assert not result1.cached

            result2 = asyncio.run(
                runner.run_prompt(prompt, provider=Provider.MOCK)
            )
            assert result2.cached
            assert result1.response_text == result2.response_text

    def test_compare_prompts(self, setup):
        p2 = Prompt(
            name="greeting2",
            messages=[Message(Role.USER, "Say hello")],
        )
        setup.save_prompt(p2)

        runner = Runner(setup)
        results = asyncio.run(
            runner.compare_prompts(
                ["greeting", "greeting2"],
                provider=Provider.MOCK,
            )
        )
        assert len(results) == 2
        assert results[0].prompt_name == "greeting"
        assert results[1].prompt_name == "greeting2"


class TestMockProvider:
    def test_mock_response(self):
        from promptsmith.providers.mock import MockProvider

        provider = MockProvider()
        result = asyncio.run(
            provider.run([Message(Role.USER, "test input")])
        )
        assert "MOCK RESPONSE" in result.response_text
        assert result.provider == Provider.MOCK
        assert result.tokens_input > 0
        assert result.tokens_output > 0
        assert result.cost_usd == 0.0
        assert result.latency_ms >= 0

    def test_mock_cost_zero(self):
        from promptsmith.providers.mock import MockProvider

        provider = MockProvider()
        assert provider.estimate_cost(1000, 500) == 0.0

    def test_mock_token_count(self):
        from promptsmith.providers.mock import MockProvider

        provider = MockProvider()
        assert provider.count_tokens("hello world") > 0
