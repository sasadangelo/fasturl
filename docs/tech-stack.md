# Technology Stack — FastURL
_Last updated: 2025-05-15_

## Overview
FastURL is a demo Python REST API built with FastAPI that demonstrates URL shortening with async background inspection. The stack is intentionally lean — chosen for clarity and educational value in a blog-article context rather than operational scale.

## System Profile
| Attribute            | Value                      |
|----------------------|----------------------------|
| System type          | REST API / web service     |
| Language             | Python 3.12                |
| Architecture pattern | Layered — by layer         |
| Deployment target    | Single process / monolith  |

## Stack Decisions
| Component          | Choice                            | Version                               | Rationale                                                                                          |
|--------------------|-----------------------------------|---------------------------------------|----------------------------------------------------------------------------------------------------|
| App framework      | FastAPI                           | ≥ 0.115, < 0.116                      | Explicitly chosen in idea.md; async-native, built-in OpenAPI, first-class Pydantic v2 support      |
| ASGI server        | Uvicorn                           | ≥ 0.34                                | Standard production-grade ASGI server for FastAPI                                                  |
| ORM / data access  | SQLAlchemy (async) + aiosqlite    | SQLAlchemy ≥ 2.0, aiosqlite ≥ 0.21   | Explicitly chosen in idea.md; async 2.x API fits FastAPI's async model; zero extra services        |
| Validation         | Pydantic v2                       | ≥ 2.3, < 3                            | Already in pyproject.toml; bundled with FastAPI; enforces strict typed DTOs                        |
| Configuration      | pydantic-settings + PyYAML        | pydantic-settings ≥ 2.2, pyyaml ≥ 6.0 | Already in pyproject.toml; typed config with YAML file + env var override                         |
| HTTP client        | httpx (AsyncClient)               | ≥ 0.28                                | Non-blocking async HTTP for background URL inspection; replaces synchronous `requests`             |
| Logging            | Loguru                            | ≥ 0.7                                 | Already in pyproject.toml; structured logging with file rotation, retention, compression           |
| Background tasks   | FastAPI BackgroundTasks           | (bundled)                             | In-process async task dispatch — zero external dependencies, fits demo scope                       |
| Testing            | pytest + pytest-asyncio + httpx   | pytest ≥ 8.4, pytest-asyncio ≥ 0.25  | pytest already in pyproject.toml; asyncio plugin needed for async route/service tests             |
| Message broker     | N/A                               | —                                     | In-process BackgroundTasks replaces a broker; adequate for single-process monolith                 |
| Containerisation   | Docker + Docker Compose           | latest stable                         | Standard local development setup; no Kubernetes needed at demo scale                               |
| Code quality       | ruff + mypy + pre-commit + bandit | already in pyproject.toml             | Full lint/format/typecheck/security pipeline already configured                                    |

## Trade-offs
- **SQLite over PostgreSQL**: Zero-dependency persistence is ideal for a demo/blog project but cannot scale horizontally. Switching to PostgreSQL later requires only a connection string change and swapping `aiosqlite` for `asyncpg`.
- **BackgroundTasks over a message broker**: Simpler and dependency-free, but tasks are lost on process restart and cannot be distributed across workers. Adequate for the demo scope.
- **requests replaced by httpx**: The existing `pyproject.toml` includes `requests` but the async inspection requirement mandates `httpx.AsyncClient`; `requests` should be removed from dependencies.

## Constraints Applied
- Demo/blog project scope → no auth, no caching, no message broker, no frontend.
- `pyproject.toml` already pins Pydantic v2, Loguru, pydantic-settings, PyYAML, ruff, mypy, pre-commit — all retained as-is.
- FastAPI explicitly named in `docs/idea.md` → no framework evaluation needed.

## Open Questions
- Should `requests` be removed from `pyproject.toml` and replaced entirely by `httpx`? *(Recommendation: yes — httpx covers both sync and async use cases.)*
- Will a `Dockerfile` and `docker-compose.yml` be scaffolded as part of `/python-framework`?

## Change Log
| Version | Date       | Change                                                                     |
|---------|------------|----------------------------------------------------------------------------|
| 0.1     | 2025-05-15 | Initial stack decision — FastAPI, SQLAlchemy async, httpx, pytest-asyncio  |
