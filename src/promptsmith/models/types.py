from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    role: Role
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role.value, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Message:
        return cls(role=Role(data["role"]), content=data["content"])


@dataclass
class Prompt:
    name: str
    messages: list[Message]
    version: int = 1
    description: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    hash: str = ""

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        content = "|".join(f"{m.role.value}:{m.content}" for m in self.messages)
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tags": self.tags,
            "metadata": self.metadata,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Prompt:
        return cls(
            name=data["name"],
            messages=[Message.from_dict(m) for m in data["messages"]],
            version=data.get("version", 1),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            hash=data.get("hash", ""),
        )


@dataclass
class RunResult:
    prompt_name: str
    prompt_version: int
    prompt_hash: str
    provider: Provider
    model: str
    messages_sent: list[Message]
    response_text: str
    tokens_input: int
    tokens_output: int
    latency_ms: float
    cost_usd: float
    cached: bool = False
    error: str | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens_total(self) -> int:
        return self.tokens_input + self.tokens_output

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "provider": self.provider.value,
            "model": self.model,
            "messages_sent": [m.to_dict() for m in self.messages_sent],
            "response_text": self.response_text,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "cached": self.cached,
            "error": self.error,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class TestCase:
    __test__ = False

    name: str
    description: str = ""
    input_variables: dict[str, str] = field(default_factory=dict)
    expected_patterns: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    min_tokens: int = 0
    max_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_variables": self.input_variables,
            "expected_patterns": self.expected_patterns,
            "forbidden_patterns": self.forbidden_patterns,
            "min_tokens": self.min_tokens,
            "max_tokens": self.max_tokens,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestCase:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            input_variables=data.get("input_variables", {}),
            expected_patterns=data.get("expected_patterns", []),
            forbidden_patterns=data.get("forbidden_patterns", []),
            min_tokens=data.get("min_tokens", 0),
            max_tokens=data.get("max_tokens", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TestResult:
    test_name: str
    prompt_name: str
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    run_result: RunResult | None = None
    error: str | None = None
    duration_ms: float = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "prompt_name": self.prompt_name,
            "passed": self.passed,
            "checks": self.checks,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class CostSummary:
    provider: Provider
    model: str
    total_calls: int
    cached_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_latency_ms: float

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.total_calls, 1)

    @property
    def avg_cost_per_call(self) -> float:
        return self.total_cost_usd / max(self.total_calls, 1)
