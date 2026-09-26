# fasturl

A Python project scaffolded from [python-blueprint](https://github.com/sasadangelo/python-blueprint).

## Setup

```bash
uv python install 3.14 && uv python pin 3.14
uv sync --group dev
```

## Run

```bash
uv run python -m fasturl.hello
```

## Test

```bash
uv run pytest tests
```

## Tools

```bash
uv run ruff check src tests/
uv run ruff format src tests/
uv run mypy src
uv run bandit -r src
pre-commit run --all-files
```
