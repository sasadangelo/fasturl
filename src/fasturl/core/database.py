# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Async SQLAlchemy engine, session factory, and FastAPI database dependency.

Usage
-----
Inject ``get_db`` into any router that needs a database session::

    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from fasturl.core.database import get_db

    @router.get("/example")
    async def example(db: AsyncSession = Depends(get_db)) -> None:
        ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from fasturl.core.config import settings
from fasturl.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Create the async engine and session factory.

    Called once at application startup from ``main.py`` lifespan.
    """
    global _engine, _session_factory

    engine_kwargs: dict[str, Any] = {
        "echo": settings.database.echo,
    }

    postgresql = settings.database.postgresql
    sqlite = settings.database.sqlite
    if postgresql is not None:
        engine_kwargs.update(
            {
                "pool_size": postgresql.pool_size,
                "max_overflow": postgresql.max_overflow,
                "pool_timeout": postgresql.pool_timeout,
                "pool_recycle": postgresql.pool_recycle,
                "pool_pre_ping": True,
            }
        )
    elif sqlite is not None:
        Path(sqlite.path).parent.mkdir(parents=True, exist_ok=True)

    _engine = create_async_engine(
        url=settings.database.url,
        **engine_kwargs,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create all tables if they do not exist yet (idempotent)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the async engine.

    Called once at application shutdown from ``main.py`` lifespan.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a per-request ``AsyncSession``.

    Yields:
        An ``AsyncSession`` that is automatically closed after the request.
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
