# Contributing to HammerDB-Scale

Thank you for your interest in contributing to HammerDB-Scale!

## Reporting Issues

Please [open an issue](https://github.com/PureStorage-OpenConnect/hammerdb-scale/issues) for:

- Bug reports (include your Python version, OS, and the full error output)
- Feature requests
- Documentation improvements

## Development Setup

```bash
# Clone the repository
git clone https://github.com/PureStorage-OpenConnect/hammerdb-scale.git
cd hammerdb-scale

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/ tests/

# Run type checker
mypy src/
```

## Running Tests

```bash
# All unit tests
pytest

# With coverage
pytest --cov=hammerdb_scale

# Specific test file
pytest tests/test_schema.py
```

## Code Style

- Python code follows [ruff](https://docs.astral.sh/ruff/) defaults
- Use snake_case for all Python identifiers and YAML config keys
- Keep CLI output user-friendly using Rich formatting helpers in `output.py`

## Pull Requests

1. Fork the repository and create a feature branch
2. Make your changes and add tests where appropriate
3. Ensure all tests pass (`pytest`) and linting is clean (`ruff check`)
4. Submit a pull request with a clear description of the change

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).
