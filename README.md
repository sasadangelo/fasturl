# FastURL

An asynchronous URL shortener built with FastAPI, SQLAlchemy 2.0 (async) and httpx.

FastURL turns long URLs into short codes and redirects visitors to the original address. After a link is created, it checks the target URL in the background: whether the page is reachable, how fast it responds, and its title, description and preview image.

## Features

- **Short links**: random 7-character Base62 codes, generated with a cryptographically secure RNG so they cannot be guessed from previous ones.
- **Custom aliases**: choose your own code (7–16 alphanumeric characters). An alias that is already taken returns `409`.
- **Expiration**: an optional `expires_at` date. Once it has passed, the link returns `410 Gone`.
- **Fast redirects**: `GET /{code}` returns a `307` redirect. Clicks are counted in a background task, after the response is sent.
- **Target inspection**: in the background, FastURL records the health status (`active` / `unreachable`), HTTP status code and latency of the target URL, plus its preview metadata (`<title>`, OpenGraph or meta description, `og:image`). You can run the inspection again at any time.
- **Listing**: filter links by inspection status and active state, and sort by `created_at` or `clicks_count`.
- **Soft delete**: deleting a link disables it, and the row stays in the database.
- **Safety**: target URLs must use HTTP or HTTPS, and URLs pointing back to FastURL itself are rejected to prevent redirect loops.
- **Operations**: every response carries an `X-Request-ID` correlation header and an `X-Process-Time` timing header, every request is written to a structured audit log, and all errors share one JSON format.
- **SQLite or PostgreSQL**: SQLite needs no setup and is the default. PostgreSQL supports multiple workers.

## Quick start

Requirements: [uv](https://docs.astral.sh/uv/) and Python 3.10–3.14.

```bash
git clone https://github.com/sasadangelo/fasturl.git
cd fasturl
uv python install 3.14 && uv python pin 3.14
uv sync
./app.sh
```

The server listens on `http://127.0.0.1:8000`. With the default SQLite backend, the database file `instance/fasturl.db` and its tables are created at the first startup.

Interactive API documentation is available at `http://127.0.0.1:8000/docs` (Swagger UI) and `http://127.0.0.1:8000/redoc`.

For local development with auto-reload:

```bash
./app.sh --reload
```

## Usage

Create a short link:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/links \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://github.com/sasadangelo/fasturl"}'
```

Optional fields: `custom_code` (your own alias) and `expires_at` (an ISO 8601 date in the future).

```json
{
  "code": "aB3x9zK",
  "short_url": "http://localhost:8000/aB3x9zK",
  "target_url": "https://github.com/sasadangelo/fasturl",
  "is_active": true,
  "expires_at": null,
  "inspection": {
    "status": "pending_analysis",
    "http_status_code": null,
    "latency_ms": null,
    "title": null,
    "description": null,
    "image_url": null,
    "last_checked_at": null
  },
  "metrics": { "clicks_count": 0, "last_clicked_at": null },
  "created_at": "2026-11-07T10:00:00",
  "updated_at": "2026-11-07T10:00:00"
}
```

The inspection runs after the response is sent, so it starts as `pending_analysis`. To see its results, read the link again:

```bash
curl http://127.0.0.1:8000/api/v1/links/aB3x9zK
```

Follow the short link:

```bash
curl -i http://127.0.0.1:8000/aB3x9zK
# HTTP/1.1 307 Temporary Redirect
# location: https://github.com/sasadangelo/fasturl
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/links` | Create a short link (`201`) |
| `GET` | `/api/v1/links` | List links. Query parameters: `status`, `is_active` (default `true`), `sort` (default `-created_at`) |
| `GET` | `/api/v1/links/{code}` | Get one link, with its metrics and inspection results |
| `DELETE` | `/api/v1/links/{code}` | Soft-delete a link (`204`) |
| `POST` | `/api/v1/links/{code}/inspect` | Run the target inspection again (`202`) |
| `GET` | `/{code}` | Redirect to the target URL (`307`) |

### Errors

All errors use the same JSON body:

```json
{
  "success": false,
  "error": "LINK_NOT_FOUND",
  "details": []
}
```

| Status | `error` | When |
|---|---|---|
| `400` | `VALIDATION_ERROR` | Invalid input; `details` lists each problem |
| `404` | `LINK_NOT_FOUND` | Unknown or deleted code |
| `409` | `ALIAS_ALREADY_TAKEN` | The custom alias is already in use |
| `410` | `LINK_EXPIRED` | The link is past its expiration date |
| `500` | `INTERNAL_SERVER_ERROR` | Unexpected error |

## Configuration

Non-secret settings are in [config.yaml](config.yaml). Secrets go in `.env`: copy [.env.example](.env.example) to `.env` to start. Environment variables override `config.yaml` and use `__` to separate nested keys, for example `APP__PORT=9000` or `DATABASE__POSTGRESQL__PASSWORD=...`.

| Section | Main settings |
|---|---|
| `app` | `host`, `port`, `workers`, `base_url` (used to build `short_url`), `code_length` |
| `database` | `echo`, and one active backend section: `sqlite` or `postgresql` |
| `log` | `level`, `console`, `file`, `rotation`, `retention`, `compression` |
| `inspector` | `timeout_seconds`, `max_redirects` |

When it starts, `app.sh` prints a summary of the configuration in effect. The database password is never printed.

### Using PostgreSQL

SQLite takes a database-wide write lock, so it must run with `workers: 1`. To run more workers, use PostgreSQL:

1. Create the database user and the database, as the PostgreSQL admin:

   ```bash
   psql -d postgres -v password='<password>' -f sql/postgres/01-init-user.sql
   ```

2. Set `DATABASE__POSTGRESQL__PASSWORD=<password>` in `.env`.
3. In `config.yaml`, comment out the `sqlite` section, uncomment `postgresql`, and set `workers` (for example `4`). The comments in that file explain how to size the connection pool.

Tables are created at startup. [sql/postgres/02-schema.sql](sql/postgres/02-schema.sql) and [sql/sqlite/schema.sql](sql/sqlite/schema.sql) contain the reference DDL.

## Docker

```bash
# SQLite
docker compose up

# PostgreSQL 17 (enable the postgresql section in config.yaml and set the password in .env first)
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up
```

The container runs as a non-root user and mounts `config.yaml`, `instance/` and `logs/` from the host.

## Development

Install the development dependencies:

```bash
uv sync --group dev
```

### Tests

```bash
uv run pytest tests                 # all tests
uv run pytest tests/unit            # unit tests only
uv run pytest tests/integration     # integration tests only
uv run pytest tests --cov --cov-branch --cov-report=term-missing
```

Unit tests use mocks. Integration tests run the real application in-process against a fresh in-memory SQLite database for each test. Outbound HTTP calls from the inspector are answered by a fake transport, so the suite never touches the network. To run the integration tests against PostgreSQL, point `TEST_DATABASE_URL` at a dedicated test database (its tables are dropped after each test):

```bash
TEST_DATABASE_URL=postgresql+asyncpg://fasturl_user:<password>@127.0.0.1:5432/fasturl_test uv run pytest
```

CI runs on GitHub Actions and fails if branch coverage drops below 85%.

### Code quality

```bash
uv run ruff check src tests/
uv run ruff format src tests/
uv run mypy src
uv run bandit -r src
pre-commit run --all-files
```

### Benchmarks

Load tests use [hey](https://github.com/rakyll/hey):

```bash
hey -n 10000 -c 50 -disable-redirects http://127.0.0.1:8000/<code>
hey -n 10000 -c 50 http://127.0.0.1:8000/api/v1/links/<code>
hey -n 1000 -c 10 -m POST -H "Content-Type: application/json" \
  -d '{"target_url": "https://www.example.com"}' http://127.0.0.1:8000/api/v1/links
```

[docs/benchmarks.md](docs/benchmarks.md) describes the methodology and the test environment, and records the baseline results.

## Project structure

```
src/fasturl/
├── main.py            # FastAPI app: lifespan, middlewares, routers
├── api/
│   ├── routers/       # HTTP endpoints (links, redirect)
│   ├── schemas/       # Pydantic request/response models
│   ├── dependencies/  # Dependency injection wiring (composition root)
│   └── middleware/    # Correlation ID, timing, audit logging
├── services/          # Business logic (LinkService, InspectorService)
├── repositories/      # Data access (LinkRepository)
├── models/            # SQLAlchemy models
└── core/              # Configuration, database, logging, exceptions
```

Each layer only calls the one below it: routers → services → repositories → database. [docs/](docs/) contains the design documents: [architecture](docs/architecture.md), [API](docs/api-design.md), [domain model](docs/domain-design.md), [database](docs/db-design.md) and [test strategy](docs/test-strategy.md).

## License

MIT. Copyright (c) 2025 Salvatore D'Angelo, Code4Projects.
