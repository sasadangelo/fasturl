# Architecture — FastURL
_Last updated: 2025-05-15_

## Overview
FastURL is a demo URL-shortening REST API built with FastAPI, designed to illustrate clean layered architecture in a real-world context for two blog articles. This document records the architectural decision and the resulting folder structure.

## Requirements Summary
| Requirement       | Value                                                              |
|-------------------|--------------------------------------------------------------------|
| Team size         | Solo / very small (1–3 people)                                     |
| Expected scale    | Small — demo/blog project, no growth pressure                      |
| Deployment model  | Single process / monolith                                          |
| Testability       | Basic — unit tests on business logic                               |
| Domain complexity | Moderate — single aggregate, embedded value objects, domain events |

## Decision
**Pattern:** `layered`
**Organisation:** by layer

## Rationale
FastURL has a single aggregate root (`Link`) with embedded value objects and two bounded contexts that communicate via in-process FastAPI `BackgroundTasks` — there is no need for the isolation overhead of hexagonal or full DDD. The `idea.md` already sketches the idiomatic FastAPI layered layout (`routers → services → repositories → schemas → core`), and a solo team on a small monolith benefits most from the simplest structure that can be explained in a blog article. Layered-by-layer keeps every concern in a named, discoverable folder without forcing readers to understand ports, adapters, or aggregate boundaries before they see any code.

## Consequences
**Positive:**
- Minimal boilerplate — every layer is a single flat folder.
- Immediately readable by FastAPI newcomers.
- Straightforward to extend for future blog articles (auth, caching, etc.).

**Trade-offs:**
- Business logic and infrastructure are not fully decoupled; swapping the DB requires changes in both `repositories/` and `core/`.
- Does not scale well beyond ~10 entities without refactoring to by-component organisation.

## Layer Map

```
src/fasturl/
├── api/
│   ├── __init__.py
│   ├── routers/
│   │   └── __init__.py        ← one router file per resource (links, redirect)
│   └── schemas/
│       └── __init__.py        ← Pydantic v2 request/response DTOs
├── services/
│   └── __init__.py            ← business logic, code generation, URL validation
├── repositories/
│   └── __init__.py            ← async SQLAlchemy data access
├── models/
│   └── __init__.py            ← SQLAlchemy ORM models (Link)
└── core/
    ├── __init__.py
    ├── config.py               ← Pydantic Settings + config.yaml loader
    └── log.py                  ← Loguru structured logging setup
```

### Layer responsibilities
| Layer / Folder   | Responsibility                                                              |
|------------------|-----------------------------------------------------------------------------|
| `api/routers/`   | HTTP transport — path/query params, status codes, BackgroundTasks dispatch  |
| `api/schemas/`   | Pydantic v2 DTOs — request validation and response serialisation            |
| `services/`      | Business rules — Base62 generation, URL safety checks, expiration logic     |
| `repositories/`  | Async DB access — SQLAlchemy sessions, CRUD queries                         |
| `models/`        | ORM models — SQLAlchemy `Link` table definition                             |
| `core/config.py` | Typed configuration — Pydantic Settings, YAML + env var overrides           |
| `core/log.py`    | Structured logging — Loguru setup with rotation, retention, compression     |

## Component Design

This section maps each functional requirement (from `docs/requirements.md`) to the layer(s) responsible for implementing it.

### JS-001 / JS-002 — Create short link (auto code or custom alias)

```
POST /api/v1/links
      │
      ▼
api/routers/links.py        ← validates HTTP request, calls service, dispatches BackgroundTask
      │
      ▼
services/link_service.py    ← generates Base62 code (or validates custom alias),
      │                        checks uniqueness, enforces URL safety rules,
      │                        builds Link entity, calls repository
      ▼
repositories/link_repo.py   ← persists Link record via async SQLAlchemy session
      │
      ▼
api/routers/links.py        ← returns HTTP 201 + dispatches BackgroundTask(inspect_link)
      │
      ▼ (async, non-blocking)
services/inspector_service.py ← performs httpx.AsyncClient request to target_url,
                                 extracts HTML title + OpenGraph tags,
                                 updates LinkInspection via repository
```

**Key rules enforced in `services/`:**
- Base62 alphabet `[a-zA-Z0-9]`, 7-char default, up to 16-char custom alias
- Collision retry loop for auto-generated codes
- Self-redirect prevention (target URL ≠ FastURL base URL)
- `expires_at > now()` if provided
- HTTP 409 if custom alias already taken

---

### JS-003 / JS-004 — Retrieve link details and list links

```
GET /api/v1/links/{code}   GET /api/v1/links?status=&page=&limit=
      │                           │
      ▼                           ▼
api/routers/links.py        ← extracts path/query params, pagination
      │
      ▼
services/link_service.py    ← applies business filters (active-only, status enum)
      │
      ▼
repositories/link_repo.py   ← async SELECT with optional WHERE + LIMIT/OFFSET
      │
      ▼
api/schemas/link_schemas.py ← serialises ORM model → Pydantic response DTO
```

---

### JS-005 — Delete / disable link

```
DELETE /api/v1/links/{code}
      │
      ▼
api/routers/links.py        ← resolves {code}, returns 404 if not found
      │
      ▼
services/link_service.py    ← sets is_active = False (soft delete)
      │
      ▼
repositories/link_repo.py   ← async UPDATE, commits session
      │
      ▼
api/routers/links.py        ← returns HTTP 204 No Content
```

---

### JS-006 — Public redirect

```
GET /{code}
      │
      ▼
api/routers/redirect.py     ← separate router mounted at root path "/"
      │
      ▼
services/link_service.py    ← resolves code → Link, checks is_active and expires_at
      │                        returns 404 (inactive), 410 (expired), or target_url
      ▼
repositories/link_repo.py   ← async UPDATE clicks_count + last_clicked_at
      │
      ▼
api/routers/redirect.py     ← returns HTTP 307 Temporary Redirect (Location: target_url)
```

---

### JS-007 — Background inspection

```
services/inspector_service.py   (triggered via FastAPI BackgroundTasks after link creation)
      │
      ├── httpx.AsyncClient.get(target_url, timeout=cfg.inspector.timeout_seconds,
      │                          follow_redirects=True, max_redirects=cfg.inspector.max_redirects)
      │
      ├── on success (2xx/3xx):  parse <title>, og:description, og:image
      │                           set status = "active"
      │
      ├── on failure (4xx/5xx / timeout / DNS error):
      │                           set status = "unreachable"
      │
      └── repositories/link_repo.py  ← async UPDATE LinkInspection snapshot on Link record
```

---

## Cross-Cutting Concerns

### Error handling

All errors follow the unified envelope `{ "success": false, "error": str, "details": list }`.
Three handlers are registered globally in `main.py`:

| Exception type             | Handler location    | HTTP status | Behaviour                                          |
|----------------------------|---------------------|-------------|----------------------------------------------------|
| `RequestValidationError`   | `core/exceptions.py` | 400         | Pydantic loc → msg array, no stack trace exposed   |
| Domain exceptions          | `core/exceptions.py` | 404/409/410 | `LinkNotFound`, `AliasAlreadyTaken`, `LinkExpired` |
| Unhandled `Exception`      | `core/exceptions.py` | 500         | Full stack trace logged to file; generic msg returned |

### Configuration

`core/config.py` loads `config.yaml` via `pydantic-settings` into a single typed `Settings` object.
Environment variables override YAML values (e.g. `DATABASE__URL`).
The app fails fast at startup if any required field is missing or malformed — no silent defaults in production paths.

```
config.yaml
    │
    ▼
core/config.py   Settings(BaseSettings)
    ├── app:     host, port, base_url, debug
    ├── database: url, echo
    ├── log:     level, console, file, rotation, retention, compression
    └── inspector: timeout_seconds, max_redirects
```

### Logging

`core/log.py` initialises Loguru once at startup (called from `main.py` lifespan).
All modules obtain a logger via `logger.bind(name=__name__)`.
Sensitive fields (target URLs in error detail, request bodies) are never logged at INFO level.

| Sink    | Level  | Rotation | Retention | Compression |
|---------|--------|----------|-----------|-------------|
| stdout  | INFO   | —        | —         | —           |
| file    | DEBUG  | 10 MB    | 7 days    | zip         |

### Async I/O

All database operations use `SQLAlchemy` 2.x async engine (`create_async_engine` + `AsyncSession`).
A single `AsyncSessionFactory` is created at startup and injected into routers via FastAPI `Depends`.
The background inspector uses `httpx.AsyncClient` with a shared client instance (created in lifespan, closed on shutdown) to avoid per-request connection overhead.

### Database session lifecycle

```
main.py (lifespan)
    └── creates AsyncEngine + AsyncSessionFactory
              │
              ▼
core/database.py   get_db() → AsyncSession   (FastAPI dependency)
              │
              ▼ injected into
api/routers/*.py   → passed down to repositories
```

---

## Request Flow Diagram

```
Client
  │
  │  HTTP request
  ▼
FastAPI app (main.py)
  │
  ├── Middleware: request logging, CORS (if needed)
  │
  ├── api/routers/links.py      ← /api/v1/links  (CRUD)
  │       │
  │       ├── api/schemas/      ← Pydantic validation (in / out)
  │       │
  │       └── services/         ← business logic
  │               │
  │               └── repositories/   ← async DB access
  │                       │
  │                       └── models/   ← SQLAlchemy ORM
  │
  ├── api/routers/redirect.py   ← /{code}  (public redirect)
  │       └── services/ → repositories/
  │
  └── core/
        ├── config.py    ← Settings (loaded once at startup)
        ├── log.py       ← Loguru (initialised once at startup)
        └── exceptions.py ← global error handlers
```

---

## Change Log
| Version | Date       | Change                                                                    |
|---------|------------|---------------------------------------------------------------------------|
| 0.1     | 2025-05-15 | Initial architecture decision — layered by layer, FastAPI monolith        |
| 0.2     | 2025-05-15 | Added Component Design, Cross-Cutting Concerns, Request Flow Diagram      |
