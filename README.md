# PromptSmith

**A prompt engineering toolkit — version control, A/B testing, caching, and evaluation for AI prompts.**

[![CI](https://github.com/user/promptsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/user/promptsmith/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

PromptSmith is a CLI tool and Python library that brings software engineering best practices to prompt development:
- **Version control** prompts like code (git-compatible YAML files)
- **A/B test** prompts across multiple AI providers simultaneously
- **Cache** responses to save API costs during development
- **Run test suites** with regex assertions and token constraints
- **Benchmark** latency and cost across models
- **Compare** prompt versions with diffs

## Installation

```bash
pip install promptsmith

# With provider support:
pip install "promptsmith[openai,anthropic]"
```

## Quick Start

```bash
# Initialize a prompt vault
promptsmith init

# Create a prompt
promptsmith create greeting \
  --system "You are a helpful assistant." \
  --user "Respond warmly to: {{topic}}"

# Run it with the mock provider (no API key needed)
promptsmith run greeting

# Create a test case
promptsmith test-add greeting-test \
  --expect "warm" \
  --forbid "error" \
  --min-tokens 10

# Run the test suite
promptsmith test greeting

# Benchmark across providers (with API keys set)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
promptsmith benchmark greeting --provider openai anthropic --model gpt-4o-mini claude-3-haiku-20240307 --runs 5

# Export/import for sharing
promptsmith export greeting -o my-prompt.yaml
promptsmith import my-prompt.yaml
```

## Architecture

```
promptsmith/
├── src/promptsmith/
│   ├── cli/              # Click CLI (20+ commands)
│   ├── core/             # Business logic
│   │   ├── vault.py      # Prompt version control (YAML + JSON index)
│   │   ├── cache.py      # SQLite response cache
│   │   ├── runner.py     # Async execution & test engine
│   │   └── evaluator.py  # Test assertion engine
│   ├── models/           # Data types (dataclasses)
│   └── providers/        # AI provider adapters
│       ├── base.py       # Abstract provider interface
│       ├── openai.py     # OpenAI (GPT-4, GPT-3.5)
│       ├── anthropic.py  # Anthropic (Claude)
│       └── mock.py       # Deterministic mock for testing
└── tests/                # Pytest test suite
```

### Key Design Decisions

- **YAML-based prompt storage** — human-readable, git-friendly, diffable
- **SQLite cache** — zero-dependency persistence, works offline
- **Async runner** — concurrent execution for benchmarks and test suites
- **Provider abstraction** — add new providers by implementing `BaseProvider`
- **Jinja2 templates** — prompt variables with `{{variable}}` syntax
- **Deterministic mock** — full testability without API keys

## Commands

### Vault Management
| Command | Description |
|---------|-------------|
| `init` | Initialize a new vault |
| `create <name>` | Create a prompt |
| `show [name]` | List prompts or show details |
| `edit <name>` | Edit prompt in $EDITOR |
| `delete <name>` | Delete a prompt |
| `export <name>` | Export to YAML file |
| `import <file>` | Import from YAML file |
| `diff <name>` | Compare versions or prompts |

### Execution
| Command | Description |
|---------|-------------|
| `run <name>` | Run prompt against a provider |
| `test <name>` | Run test suite |
| `benchmark <name>` | Benchmark across providers |
| `compare` | Compare multiple prompts |

### Cache & Config
| Command | Description |
|---------|-------------|
| `cache stats` | Show cache statistics |
| `cache clear` | Clear cache |
| `cache prune` | Prune old entries |
| `config get/set` | Manage vault config |

## Prompt Format

Prompts are stored as versioned YAML files:

```yaml
# .promptsmith/prompts/example/v001.yaml
name: example
version: 1
description: "Analyzes user sentiment"
tags: [sentiment, analysis]
messages:
  - role: system
    content: "You are a sentiment analysis expert."
  - role: user
    content: "Analyze the sentiment of: {{text}}"
hash: a1b2c3d4e5f6
```

## Test Cases

Define tests in `.promptsmith/tests/`:

```yaml
# .promptsmith/tests/sentiment-check.yaml
name: sentiment-check
description: "Verify sentiment detection works"
input_variables:
  text: "I absolutely love this product!"
expected_patterns:
  - "positive"
  - "love"
forbidden_patterns:
  - "negative"
  - "error"
min_tokens: 5
max_tokens: 200
```

## Provider Pricing (per 1M tokens)

| Provider | Model | Input | Output |
|----------|-------|-------|--------|
| OpenAI | gpt-4o | $2.50 | $10.00 |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 |
| OpenAI | gpt-4-turbo | $10.00 | $30.00 |
| Anthropic | Claude 3.5 Sonnet | $3.00 | $15.00 |
| Anthropic | Claude 3 Haiku | $0.25 | $1.25 |

## Development

```bash
git clone https://github.com/user/promptsmith.git
cd promptsmith
pip install -e ".[dev]"
pytest
ruff check .
mypy src/
```

## License

MIT — see [LICENSE](LICENSE)
