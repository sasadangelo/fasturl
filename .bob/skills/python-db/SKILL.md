---
name: python-db
description: Use when implementing the database layer of a Python project — creates the async SQLAlchemy engine/session factory (core/database.py), ORM models (<Entity>DAO in models/), and repository classes (repositories/). Run after /db-design and before /python-api or any other skill that needs direct DB access. Framework-agnostic — works for REST APIs, web apps, CLIs, and any other project type that accesses a relational DB directly.
metadata:
  argument-hint: "[entity or domain description]"
---

# Python Database Layer Implementation

This skill implements the database access layer of a Python project using **SQLAlchemy** (async
or sync, depending on `docs/architecture.md`).

It produces exactly three categories of artefact — nothing more:

| Artefact | Description |
|---|---|
| `src/<pkg>/core/database.py` | Engine, session factory, `init_db()`, `close_db()`, `get_db()` |
| `src/<pkg>/models/<entity>.py` | SQLAlchemy ORM model (`<Entity>DAO`) per table |
| `src/<pkg>/repositories/<entity>_repository.py` | Data-access repository per aggregate root |

This skill does **not** touch routers, services, Pydantic schemas, middlewares, or any other
layer. Those belong to `/python-api`, `/python-web`, or other delivery-layer skills.

---

## Phase 0 — Check Prerequisites

### Step 0.1 — DB design documents (required)

```
glob: docs/db-design/README.md
glob: docs/db-design.md
glob: sql/schema.sql
```

Read whichever doc exists (folder README takes priority). Also read `sql/schema.sql` if present.

**If neither `docs/db-design.md` nor `sql/schema.sql` exists:**
- Stop immediately and tell the user:
  _"No database design found. `/python-db` requires `docs/db-design.md` and/or `sql/schema.sql`
  as its primary input. Please run `/db-design` first to produce the schema, then come back and
  run `/python-db`."_
- Do not proceed further.

**If found:**
- Extract: DB engine, tables with columns and types, FK relationships, unique indexes,
  check constraints, PK strategy.

### Step 0.2 — Architecture document (required)

```
glob: docs/architecture/README.md
glob: docs/architecture.md
```

Read whichever exists (folder README takes priority).

**If not found:**
- Stop immediately and tell the user:
  _"No architecture document found. `/python-db` requires `docs/architecture.md` to determine
  the async model, DB driver, and ORM configuration. Please run `/architecture` first."_
- Do not proceed further.

**If found:**
- Extract: async model (`asyncio` vs sync), DB engine (SQLite / PostgreSQL / MySQL),
  async driver (`aiosqlite`, `asyncpg`, `aiomysql`), ORM (`SQLAlchemy`, `Tortoise`, other),
  connection pool settings if specified.

### Step 0.3 — Domain design (required)

```
glob: docs/domain-design/README.md
glob: docs/domain-design.md
```

**If not found:**
- Stop immediately and tell the user:
  _"No domain design found. `/python-db` requires `docs/domain-design.md` to map domain entities
  to ORM models. Please run `/domain-design` first."_
- Do not proceed further.

**If found:**
- Extract: entities, aggregates, value objects — used to decide which tables map to Aggregate
  Root DAOs and which are embedded columns vs separate models.

### Step 0.4 — Scaffold readiness

```
glob: pyproject.toml
glob: src/*/
```

If `pyproject.toml` or `src/<pkg>/` are missing, stop and tell the user:
_"The project scaffold is not ready. Please run `/python-init <project-name>` first."_

### Step 0.5 — Existing DB artefacts detection

Scan for already-implemented DB layer artefacts:

```
grep: "class.*DAO" in src/
grep: "DeclarativeBase|mapped_column|Column(" in src/
grep: "__tablename__" in src/
grep: "async_sessionmaker|create_async_engine|create_engine" in src/
```

**If ORM models or session factory already exist:**
- Tell the user: _"I found an existing DB layer: `<list of files>`. I'll reverse-engineer the
  current implementation."_
- Show a summary table of found models (class name → table name) and the session factory location.
- Ask:

  ```
  ask_followup_question: "What would you like to do?"
  suggestion_a: "Add a new ORM model and repository for a new entity"
  suggestion_b: "Update an existing model (add/rename columns)"
  suggestion_c: "Regenerate the full DB layer from the current db-design"
  suggestion_d: "Only add/update the session factory (core/database.py)"
  ```

  Jump to the relevant phase. Do NOT regenerate artefacts that have not changed.

**If nothing found:** proceed through all phases.

---

## Phase 1 — Dependencies

### Step 1.1 — Resolve required packages

From `docs/architecture.md` determine the required packages:

| Scenario | Packages |
|---|---|
| Async + SQLite | `sqlalchemy[asyncio]`, `aiosqlite` |
| Async + PostgreSQL | `sqlalchemy[asyncio]`, `asyncpg` |
| Async + MySQL / MariaDB | `sqlalchemy[asyncio]`, `aiomysql` |
| Sync + SQLite | `sqlalchemy` |
| Sync + PostgreSQL | `sqlalchemy`, `psycopg2-binary` |

### Step 1.2 — Add missing dependencies

Check `pyproject.toml`. For each required package not already present:

```
execute_command: uv add <package>
```

---

## Phase 2 — Session Factory (`core/database.py`)

### Step 2.1 — Determine async vs sync

- **Async** (default for FastAPI / async frameworks): use `create_async_engine` +
  `async_sessionmaker[AsyncSession]`
- **Sync** (batch scripts, simple CLIs): use `create_engine` + `sessionmaker[Session]`

### Step 2.2 — Write `src/<pkg>/core/database.py`

**If the file does not exist:** create it.
**If it exists:** patch only what changed with `apply_diff`.

#### Async template

```python
"""Async SQLAlchemy engine, session factory, and database dependency.

Usage
-----
Inject ``get_db`` wherever a database session is needed::

    from <pkg>.core.database import get_db

    async def example(db: AsyncSession = Depends(get_db)) -> None:
        ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from <pkg>.core.config import settings
from <pkg>.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Create the async engine and session factory.

    Called once at application startup (lifespan or CLI bootstrap).
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        url=settings.database.url,
        echo=settings.database.echo,
        pool_size=getattr(settings.database, "pool_size", 20),
        max_overflow=getattr(settings.database, "max_overflow", 10),
        pool_timeout=30,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the async engine.

    Called once at application shutdown.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a per-request ``AsyncSession``.

    Rolls back automatically on exception; always closes on exit.
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialised — call init_db() at startup.")
    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

#### Sync template

Same structure but replace async primitives:
- `create_async_engine` → `create_engine`
- `async_sessionmaker[AsyncSession]` → `sessionmaker[Session]`
- `async def init_db()` → `def init_db()`
- `async def close_db()` → `def close_db()`
- `async def get_db()` → `def get_db()` (yields `Session`)

### Step 2.3 — Update `models/__init__.py`

Ensure `Base` is exported from `src/<pkg>/models/__init__.py` so `database.py` can import it
cleanly. If the file does not exist, create it:

```python
from <pkg>.models.<first_entity> import Base

__all__ = ["Base"]
```

---

## Phase 3 — ORM Models (`models/<entity>.py`)

One file per table. Each ORM class is named **`<Entity>DAO`** — never `<Entity>`, `<Entity>Model`,
or `<Entity>ORM`.

### Step 3.1 — Naming conventions (mandatory)

| Object | Convention | Example |
|---|---|---|
| ORM class | `<Entity>DAO` | `LinkDAO` |
| File | `models/<entity>.py` | `models/link.py` |
| Table attribute | `__tablename__` = plural snake_case | `"links"` |
| PK | `id` — internal only, never exposed via API | |
| External identifier | named after domain role (`code`, `slug`, `public_id`) | `code` |

**The DAO suffix is mandatory.** It signals that this class is a data-access object, not a domain
entity. External layers (routers, services) must never import DAOs directly — they interact
through repositories or DTOs.

### Step 3.2 — Column mapping rules

| Domain concept | SQLAlchemy type | Notes |
|---|---|---|
| Short string (bounded) | `String(n)` | Use `n` from `db-design.md` |
| Long / unbounded text | `Text` | |
| Integer counter / FK | `Integer` | |
| Large integer PK | `Integer` (SQLite) / `BigInteger` (PG) | |
| Boolean | `Boolean` | SQLite stores as `INTEGER` transparently |
| Float / latency | `Float` | |
| Decimal / money | `Numeric(p, s)` | Never `Float` for money |
| Datetime (no tz) | `DateTime` | Store UTC, strip `tzinfo` before persist |
| Datetime (with tz) | `DateTime(timezone=True)` | PostgreSQL `TIMESTAMPTZ` |
| Optional column | `nullable=True` | |
| Required column | `nullable=False` | Default for all columns |

Value Objects from the domain design that are embedded in the owning table appear as **flat
columns** with a comment grouping them (see template below).

### Step 3.3 — ORM model template

```python
"""SQLAlchemy ORM model for the ``<table>`` table.

``<Entity>DAO`` is a data-access object — only the repository layer is
permitted to import it. External layers interact through the repository
facade or response DTOs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class <Entity>DAO(Base):
    """ORM representation of the ``<table>`` table.

    Attributes:
        id: Internal surrogate PK — never exposed externally.
        <attr>: <description>.
        created_at: Record creation timestamp (UTC).
        updated_at: Record last-modification timestamp (UTC).
    """

    __tablename__ = "<table>"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- <ValueObject> VO — embedded columns ---
    <col>: Mapped[<type>] = mapped_column(<SQLAType>, nullable=False)
    <opt_col>: Mapped[<type> | None] = mapped_column(<SQLAType>, nullable=True, default=None)

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
```

**Rules:**
- `Base` is defined in the **first** model file only. All subsequent models import it from there
  or from `models/__init__.py`.
- `created_at` and `updated_at` are present on every table.
- `onupdate` on `updated_at` ensures automatic timestamp refresh on every UPDATE.
- Integer PKs use `autoincrement=True`; they are internal and never returned via API.
- Columns with `unique=True` also set `index=True`.

### Step 3.4 — Multiple tables

When the schema has more than one table:
- `Base` lives in the first entity file (or in a dedicated `models/base.py`)
- Every other model imports `Base` from that location
- `models/__init__.py` re-exports `Base` and all DAO classes

```python
# models/__init__.py
from <pkg>.models.<first>.py import Base
from <pkg>.models.<first>.py import <First>DAO
from <pkg>.models.<second>.py import <Second>DAO

__all__ = ["Base", "<First>DAO", "<Second>DAO"]
```

---

## Phase 4 — Repositories (`repositories/<entity>_repository.py`)

One repository class per **Aggregate Root** (not per table). Junction tables or embedded value
objects do not get their own repository.

### Step 4.1 — Naming conventions (mandatory)

| Object | Convention | Example |
|---|---|---|
| Class | `<Entity>Repository` | `LinkRepository` |
| File | `repositories/<entity>_repository.py` | `repositories/link_repository.py` |
| Constructor arg | `session: AsyncSession` (or `Session`) | |

### Step 4.2 — Repository rules (hard boundaries)

1. **Data access only.** No business rules, no status calculations, no pricing logic.
   A repository answers only: *"How do I store or retrieve this DAO record?"*
2. **Import only the DAO.** Never import service classes, Pydantic schemas, or router objects.
3. **Explicit column projections** when only a subset of columns is needed (avoid `SELECT *`
   on hot paths).
4. **Allowlist sort columns** to prevent SQL injection via dynamic `ORDER BY`.
5. **Atomic counters** via SQL expression (`col + 1`), never read-modify-write in Python.

### Step 4.3 — Standard method set

Implement the methods that match the query patterns in `docs/db-design.md` (Index Plan section)
and `docs/api-design.md` (if present). Minimum set for a CRUD aggregate:

| Method | Signature | Description |
|---|---|---|
| `get_by_<key>` | `async def get_by_<key>(self, val) -> <Entity>DAO \| None` | Fetch by unique key |
| `list_<entities>` | `async def list_<entities>(self, **filters) -> list[<Entity>DAO]` | Filtered + sorted list |
| `create` | `async def create(self, dao: <Entity>DAO) -> <Entity>DAO` | INSERT + refresh |
| `update_<concern>` | `async def update_<concern>(self, key, **values) -> bool` | Partial UPDATE |
| `soft_delete` | `async def soft_delete(self, key) -> bool` | Set `is_active = False` |
| `<key>_exists` | `async def <key>_exists(self, val) -> bool` | Existence check (SELECT id only) |

Add domain-specific methods as needed (e.g. `increment_clicks`, `update_inspection`).

### Step 4.4 — Repository template (async)

```python
"""Async SQLAlchemy repository for the ``<Entity>DAO`` aggregate.

Data-access only — no business rules, no status calculations.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from <pkg>.models.<entity> import <Entity>DAO


class <Entity>Repository:
    """Data-access layer for the ``<table>`` table.

    Args:
        session: An injected async SQLAlchemy session for the current request.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_<key>(self, <key>: <type>) -> <Entity>DAO | None:
        """Return the ``<Entity>DAO`` with the given <key>, or ``None``.

        Args:
            <key>: <description>.

        Returns:
            The matching ``<Entity>DAO`` instance, or ``None``.
        """
        result = await self._session.execute(
            select(<Entity>DAO).where(<Entity>DAO.<key> == <key>)
        )
        return result.scalar_one_or_none()

    async def create(self, dao: <Entity>DAO) -> <Entity>DAO:
        """Persist a new record and return the refreshed instance.

        Args:
            dao: A fully-constructed (not yet persisted) ``<Entity>DAO`` instance.

        Returns:
            The ``<Entity>DAO`` after INSERT with server-generated values populated.
        """
        self._session.add(dao)
        await self._session.commit()
        await self._session.refresh(dao)
        return dao

    async def <key>_exists(self, <key>: <type>) -> bool:
        """Return ``True`` if any record uses the given <key>.

        Args:
            <key>: <description>.
        """
        result = await self._session.execute(
            select(<Entity>DAO.id).where(<Entity>DAO.<key> == <key>)
        )
        return result.scalar_one_or_none() is not None
```

---

## Phase 5 — Validation

Run in order after writing all artefacts:

```
execute_command: ruff check src/ && ruff format src/
execute_command: mypy src/
```

Fix all errors before declaring done.

Optionally run a smoke import test:

```
execute_command: uv run python -c "from <pkg>.core.database import init_db, get_db; print('DB layer OK')"
```

---

## Phase 6 — Report

After all artefacts are written and validation passes, report:

- Files created or updated
- List of DAO classes and their table names
- List of repository classes and their key methods
- Prompt the user for the next step:

  ```
  ask_followup_question: "What would you like to work on next?"
  suggestion_a: "Implement the REST API layer — run /python-api"
  suggestion_b: "Add another entity (ORM model + repository)"
  suggestion_c: "Define Alembic migrations for schema versioning"
  suggestion_d: "The DB layer is complete for now"
  ```

---

## Conventions reference

### Naming (mandatory)

| Object | Convention | Example |
|---|---|---|
| ORM class | `<Entity>DAO` | `LinkDAO` |
| Repository class | `<Entity>Repository` | `LinkRepository` |
| Model file | `models/<entity>.py` | `models/link.py` |
| Repository file | `repositories/<entity>_repository.py` | `repositories/link_repository.py` |
| `Base` export | `models/__init__.py` | `from pkg.models import Base` |
| Table name | plural snake_case | `"links"` |
| PK | `id` | always internal |
| External key | domain-meaningful name | `code`, `slug`, `public_id` |

### What this skill does NOT generate

| Artefact | Belongs to |
|---|---|
| `core/config/database.py` (Settings) | `/python-config` or `/python-init` |
| Alembic migration files | future `/python-migrate` skill |
| Pydantic request/response schemas | `/python-api` |
| FastAPI routers and dependencies | `/python-api` |
| Service layer | `/python-api` or `/python-web` |
| CLI commands | `/python-cli` |
