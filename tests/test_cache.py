from __future__ import annotations

import json
import tempfile

import pytest

from promptsmith.core.cache import Cache
from promptsmith.models.types import Message, Provider, Role, RunResult


@pytest.fixture
def cache():
    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        c = Cache(tf.name)
        yield c


class TestCache:
    def test_init_creates_db(self, cache):
        assert cache.db_path.exists()

    def test_set_and_get(self, cache):
        result = RunResult(
            prompt_name="test",
            prompt_version=1,
            prompt_hash="abc123",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[Message(Role.USER, "hello")],
            response_text="world",
            tokens_input=10,
            tokens_output=5,
            latency_ms=100,
            cost_usd=0.001,
        )
        msgs_json = json.dumps(
            [{"role": "user", "content": "hello"}], sort_keys=True
        )

        cache.set(result, msgs_json)
        cached = cache.get("abc123", "mock", "mock", msgs_json)
        assert cached is not None
        assert cached.response_text == "world"
        assert cached.tokens_input == 10
        assert cached.cached is True

    def test_get_miss(self, cache):
        msgs_json = json.dumps([{"role": "user", "content": "nope"}], sort_keys=True)
        assert cache.get("xyz", "mock", "mock", msgs_json) is None

    def test_invalidate(self, cache):
        result = RunResult(
            prompt_name="t",
            prompt_version=1,
            prompt_hash="hash1",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="resp",
            tokens_input=1,
            tokens_output=1,
            latency_ms=10,
            cost_usd=0,
        )
        msgs_json = json.dumps([{"role": "user", "content": "a"}], sort_keys=True)
        cache.set(result, msgs_json)

        result2 = RunResult(
            prompt_name="t2",
            prompt_version=1,
            prompt_hash="hash2",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="resp2",
            tokens_input=1,
            tokens_output=1,
            latency_ms=10,
            cost_usd=0,
        )
        msgs_json2 = json.dumps([{"role": "user", "content": "b"}], sort_keys=True)
        cache.set(result2, msgs_json2)

        count = cache.invalidate("hash1")
        assert count == 1

        assert cache.get("hash1", "mock", "mock", msgs_json) is None
        assert cache.get("hash2", "mock", "mock", msgs_json2) is not None

    def test_stats(self, cache):
        result = RunResult(
            prompt_name="s",
            prompt_version=1,
            prompt_hash="s_hash",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="ok",
            tokens_input=5,
            tokens_output=3,
            latency_ms=50,
            cost_usd=0.002,
        )
        msgs_json = json.dumps([{"role": "user", "content": "s"}], sort_keys=True)
        cache.set(result, msgs_json)
        cache.set(result, msgs_json)

        stats = cache.stats()
        assert stats["total_entries"] >= 1
        assert stats["cost_saved_usd"] >= 0.002

    def test_prune(self, cache):
        result = RunResult(
            prompt_name="p",
            prompt_version=1,
            prompt_hash="p_hash",
            provider=Provider.MOCK,
            model="mock",
            messages_sent=[],
            response_text="old",
            tokens_input=1,
            tokens_output=1,
            latency_ms=1,
            cost_usd=0,
        )
        msgs_json = json.dumps([{"role": "user", "content": "p"}], sort_keys=True)
        cache.set(result, msgs_json)

        count = cache.prune(max_age_days=365)
        assert count == 0

        count = cache.prune(max_age_days=0)
        assert count >= 0
