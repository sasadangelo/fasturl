# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Shared pytest fixtures for unit and integration tests.

Unit fixtures: async-capable stubs for LinkRepository and httpx.AsyncClient.
Integration fixtures: in-memory SQLite engine, real AsyncSession, FastAPI
ASGI client with the DB dependency overridden.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx._transports.asgi import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from fasturl.core.database import get_db
from fasturl.main import app
from fasturl.models.link import Base

# ---------------------------------------------------------------------------
# Integration — in-memory SQLite engine and session
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession backed by a fresh in-memory SQLite database.

    Creates all tables before the test and drops them after, ensuring full
    isolation between tests.
    """
    engine: AsyncEngine = create_async_engine(url="sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(fn=Base.metadata.create_all)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Integration — FastAPI ASGI client with DB dependency overridden
# ---------------------------------------------------------------------------


@pytest.fixture()
async def api_client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """Yield an httpx.AsyncClient driving the FastAPI app in-process.

    The ``get_db`` dependency is overridden to inject the test session so that
    every request shares the same in-memory database as the test body.

    A stub httpx.AsyncClient is stored on ``app.state.http_client`` so that the
    ``HTTPClientDep`` dependency resolves without a real lifespan.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.state.http_client = httpx.AsyncClient()  # stub; intercepted per-test via respx

    transport: ASGITransport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await app.state.http_client.aclose()


# ---------------------------------------------------------------------------
# Unit — mock LinkRepository
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repository() -> AsyncMock:
    """Return an AsyncMock that stands in for LinkRepository in unit tests."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# Unit — mock httpx.AsyncClient for inspector tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_http_client() -> AsyncMock:
    """Return an AsyncMock that stands in for httpx.AsyncClient in inspector unit tests."""
    return AsyncMock()
