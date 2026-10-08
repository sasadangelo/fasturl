# fasturl

A Python project scaffolded from [python-blueprint](https://github.com/sasadangelo/python-blueprint).

## Setup

```bash
uv python install 3.14 && uv python pin 3.14
uv sync --group dev
```

## Run

```bash
./app.sh
# or with auto-reload:
./app.sh --reload
```

## Benchmarks

Load benchmarks are executed using [`hey`](https://github.com/rakyll/hey):

```bash
# Install hey
brew install hey

# Run benchmarks against local server
hey -n 10000 -c 50 -disable-redirects http://127.0.0.1:8000/<code>
hey -n 10000 -c 50 http://127.0.0.1:8000/api/v1/links/<code>
hey -n 1000 -c 10 -m POST -H "Content-Type: application/json" -d '{"target_url": "https://www.example.com"}' http://127.0.0.1:8000/api/v1/links
```

See [docs/benchmarks.md](docs/benchmarks.md) for detailed methodology, test environment parameters, and historical benchmark baselines.

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
