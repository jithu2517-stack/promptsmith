from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from jinja2 import Template

from promptsmith.core.cache import Cache
from promptsmith.core.vault import Vault
from promptsmith.models.types import (
    Message,
    Prompt,
    Provider,
    Role,
    RunResult,
    TestCase,
    TestResult,
)
from promptsmith.providers import get_provider
from promptsmith.providers.base import BaseProvider


class Runner:
    """Executes prompts against AI providers with caching and testing support."""

    def __init__(
        self,
        vault: Vault | None = None,
        cache: Cache | None = None,
    ) -> None:
        self.vault = vault or Vault()
        self.cache = cache or Cache()

    def _render_prompt(self, prompt: Prompt, variables: dict[str, str]) -> Prompt:
        """Render template variables in prompt messages."""
        rendered_messages = []
        for msg in prompt.messages:
            try:
                content = Template(msg.content).render(**variables)
            except Exception:
                content = msg.content
            rendered_messages.append(Message(role=msg.role, content=content))
        return Prompt(
            name=prompt.name,
            messages=rendered_messages,
            version=prompt.version,
            description=prompt.description,
            tags=prompt.tags,
            metadata=prompt.metadata,
            hash=prompt.hash,
        )

    async def run_prompt(
        self,
        prompt: Prompt,
        provider: Provider | str = Provider.MOCK,
        model: str | None = None,
        no_cache: bool = False,
        variables: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> RunResult:
        """Run a prompt against a provider with caching."""
        if variables:
            prompt = self._render_prompt(prompt, variables)

        if isinstance(provider, str):
            provider = Provider(provider)

        prov = get_provider(provider, model)

        messages_json = json.dumps(
            [m.to_dict() for m in prompt.messages], sort_keys=True
        )

        if not no_cache:
            cached = self.cache.get(
                prompt.hash, provider.value, prov.model, messages_json
            )
            if cached:
                cached.prompt_name = prompt.name
                cached.prompt_version = prompt.version
                return cached

        result = await prov.run(prompt.messages, **kwargs)
        result.prompt_name = prompt.name
        result.prompt_version = prompt.version
        result.prompt_hash = prompt.hash

        self.cache.set(result, messages_json)

        return result

    async def run_test(
        self,
        prompt_name: str,
        test_name: str,
        provider: Provider | str = Provider.MOCK,
        model: str | None = None,
        no_cache: bool = False,
    ) -> TestResult:
        """Run a single test case."""
        from promptsmith.core.evaluator import evaluate_test_case

        prompt = self.vault.get_prompt(prompt_name)
        if not prompt:
            raise ValueError(f"Prompt '{prompt_name}' not found in vault.")

        test_case = self.vault.get_test(test_name)
        if not test_case:
            raise ValueError(f"Test '{test_name}' not found in vault.")

        start = time.monotonic()
        run_result = await self.run_prompt(
            prompt,
            provider=provider,
            model=model,
            no_cache=no_cache,
            variables=test_case.input_variables,
        )
        duration = (time.monotonic() - start) * 1000

        result = evaluate_test_case(test_case, run_result)
        result.duration_ms = duration
        return result

    async def run_test_suite(
        self,
        prompt_name: str,
        provider: Provider | str = Provider.MOCK,
        model: str | None = None,
        no_cache: bool = False,
        test_filter: str | None = None,
    ) -> list[TestResult]:
        """Run all tests for a prompt."""
        test_names = self.vault.list_tests()
        if test_filter:
            test_names = [t for t in test_names if test_filter in t]

        tasks = []
        for test_name in test_names:
            tasks.append(
                self.run_test(
                    prompt_name=prompt_name,
                    test_name=test_name,
                    provider=provider,
                    model=model,
                    no_cache=no_cache,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = []
        for r in results:
            if isinstance(r, Exception):
                output.append(
                    TestResult(
                        test_name="error",
                        prompt_name=prompt_name,
                        passed=False,
                        error=str(r),
                    )
                )
            else:
                output.append(r)
        return output

    async def compare_prompts(
        self,
        prompt_names: list[str],
        provider: Provider | str = Provider.MOCK,
        model: str | None = None,
        variables: dict[str, str] | None = None,
    ) -> list[RunResult]:
        """Run multiple prompts and return results for comparison."""
        tasks = []
        for name in prompt_names:
            prompt = self.vault.get_prompt(name)
            if not prompt:
                continue
            tasks.append(
                self.run_prompt(
                    prompt,
                    provider=provider,
                    model=model,
                    variables=variables,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, RunResult)]

    async def benchmark_prompt(
        self,
        prompt_name: str,
        providers: list[tuple[Provider, str]],
        variables: dict[str, str] | None = None,
        runs: int = 3,
    ) -> list[RunResult]:
        """Run a prompt against multiple providers/models for comparison."""
        prompt = self.vault.get_prompt(prompt_name)
        if not prompt:
            raise ValueError(f"Prompt '{prompt_name}' not found in vault.")

        all_results = []
        for _ in range(runs):
            tasks = []
            for prov, model in providers:
                tasks.append(
                    self.run_prompt(
                        prompt,
                        provider=prov,
                        model=model,
                        no_cache=True,
                        variables=variables,
                    )
                )
            batch = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(r for r in batch if isinstance(r, RunResult))

        return all_results
