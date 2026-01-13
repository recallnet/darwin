# Contributing to Darwin

Thank you for your interest in contributing to Darwin! This document provides guidelines and instructions for contributing.

## Code Style

### Python Style Guide

Darwin follows strict code quality standards:

- **Formatting**: Code is formatted with [Black](https://black.readthedocs.io/) (line length: 100)
- **Linting**: Code is linted with [Ruff](https://github.com/astral-sh/ruff)
- **Type Checking**: All code must pass [mypy](https://mypy.readthedocs.io/) type checking
- **Documentation**: All public functions, classes, and modules must have docstrings

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality. Install them with:

```bash
pip install pre-commit
pre-commit install
```

This will automatically run Black, Ruff, and mypy before each commit.

## Testing Requirements

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=darwin --cov-report=html

# Run specific test file
pytest tests/unit/test_simulator.py

# Run specific test
pytest tests/unit/test_simulator.py::TestPosition::test_stop_loss_hit_long

# Run only fast tests (skip slow/integration tests)
pytest -m "not slow"
```

### Test Coverage

- **Minimum coverage**: 80% overall
- **Critical modules**: 90% coverage required for:
  - Simulator logic (position, exits)
  - Storage layer (candidate_cache, position_ledger)
  - Schema validation

### Writing Tests

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test component interactions
- **Property-based tests**: Use Hypothesis for invariant testing (especially simulator logic)

Example test structure:

```python
def test_feature_name():
    """Test that feature works as expected."""
    # Arrange
    input_data = create_test_data()

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_value
```

## Pull Request Process

### Before Submitting

1. **Update tests**: Add/update tests for your changes
2. **Run test suite**: Ensure all tests pass
3. **Check coverage**: Verify coverage doesn't decrease
4. **Format code**: Run Black and Ruff
5. **Type check**: Run mypy
6. **Update docs**: Update relevant documentation

### PR Guidelines

- **Title**: Use descriptive title (e.g., "Add trailing stop invariant tests")
- **Description**: Explain what changed and why
- **Link issues**: Reference any related issues
- **Small PRs**: Keep PRs focused and reviewable

### PR Checklist

- [ ] Tests added/updated
- [ ] All tests passing
- [ ] Code formatted with Black
- [ ] No Ruff warnings
- [ ] mypy passes
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for notable changes)

## Development Workflow

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/recallnet/darwin.git
cd darwin

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
pytest
```

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `test/description` - Test additions/improvements
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Messages

Use clear, descriptive commit messages:

```
Add trailing stop invariant tests

- Test that trailing stop never decreases
- Test that trailing stop stays within distance
- Add property-based tests with Hypothesis
```

## Architecture Guidelines

### Separation of Concerns

- **Playbooks**: Pure functions (features → candidate decision)
- **LLM**: Evaluative decision-making only
- **Simulator**: Execution semantics (how trades perform)
- **Storage**: Single source of truth (no derived caching)

### Immutability

- All artifacts include version headers
- Configs are snapshotted (never mutated)
- Position ledger is append-only

### Error Handling

- Fail fast on invalid configs
- Graceful degradation for LLM failures
- Comprehensive logging

## Code Review Standards

### What Reviewers Look For

- **Correctness**: Does it work as intended?
- **Tests**: Adequate test coverage?
- **Style**: Follows code style guide?
- **Performance**: Efficient implementation?
- **Clarity**: Easy to understand?

### Giving Feedback

- Be constructive and specific
- Explain the "why" behind suggestions
- Distinguish between "must fix" and "nice to have"

## Getting Help

- **Issues**: Open a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check docs/ directory

## License

By contributing to Darwin, you agree that your contributions will be licensed under the MIT License.
