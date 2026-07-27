# Contributing to PromptSmith

## Getting Started

1. Fork the repository
2. Clone your fork
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Create a branch: `git checkout -b feature/my-feature`
5. Make changes and add tests
6. Run tests: `pytest`
7. Run linting: `ruff check .`
8. Submit a PR

## Project Structure

```
src/promptsmith/
├── cli/          # User-facing CLI commands
├── core/         # Business logic (vault, cache, runner, evaluator)
├── models/       # Data types and serialization
└── providers/    # AI provider integrations
```

## Adding a New Provider

1. Create `src/promptsmith/providers/myprovider.py`
2. Implement the `BaseProvider` abstract class
3. Register in `PROVIDER_MAP` in `__init__.py`
4. Add pricing in the provider class
5. Add tests in `tests/test_providers.py`

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=promptsmith

# Skip slow/integration tests
pytest -m "not slow and not integration"
```

## Code Style

- Python 3.10+ with type hints
- Follow existing patterns for error handling
- Use `async/await` for all provider calls
- Data classes for models, no ORM outside cache
- Rich for terminal output, Click for CLI

## Commit Messages

Follow conventional commits:
- `feat: add benchmark command`
- `fix: correct cost calculation`
- `docs: update README`
- `test: add vault diff tests`
