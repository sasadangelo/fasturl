# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Shared pytest fixtures for unit and integration tests.

Unit fixtures: async-capable stubs for LinkRepository and httpx.AsyncClient.
Integration fixtures: real database engine and AsyncSession, a fake HTTP
client for the inspector, FastAPI ASGI client with both dependencies overridden.

Integration tests use an in-memory SQLite database by default. Set
``TEST_DATABASE_URL`` to run them against another database, e.g. PostgreSQL::

    TEST_DATABASE_URL=postgresql+asyncpg://fasturl_user:<password>@127.0.0.1:5432/fasturl_test uv run pytest

The target database must exist and be dedicated to tests: tables are created
before each test and dropped after it.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from fasturl.api.dependencies import get_http_client
from fasturl.core.database import get_db
from fasturl.main import app
from fasturl.models.link import Base

# ---------------------------------------------------------------------------
# Integration — database engine and session
# ---------------------------------------------------------------------------

TEST_DATABASE_URL: str = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture()
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession backed by a fresh test database (``TEST_DATABASE_URL``).

    Creates all tables before the test and drops them after, ensuring full
    isolation between tests.
    """
    engine: AsyncEngine = create_async_engine(url=TEST_DATABASE_URL, echo=False)
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
# Integration — fake outside world for the background inspector
# ---------------------------------------------------------------------------

FAKE_PAGE: str = "<html><head><title>Example Domain</title></head></html>"


def _fake_target(request: httpx.Request) -> httpx.Response:
    """Answer every outbound request with a small HTML page."""
    return httpx.Response(status_code=200, text=FAKE_PAGE)


@pytest.fixture()
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield an httpx.AsyncClient whose network layer never leaves the process."""
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler=_fake_target)) as client:
        yield client


# ---------------------------------------------------------------------------
# Integration — FastAPI ASGI client with dependencies overridden
# ---------------------------------------------------------------------------


@pytest.fixture()
async def api_client(db_session: AsyncSession, http_client: httpx.AsyncClient) -> AsyncIterator[httpx.AsyncClient]:
    """Yield an httpx.AsyncClient driving the FastAPI app in-process.

    The ``get_db`` dependency is overridden to inject the test session so that
    every request shares the same in-memory database as the test body.

    The ``get_http_client`` dependency is overridden with the ``http_client``
    fixture, so the background inspector never makes a real network call.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_http_client] = lambda: http_client

    transport: httpx.ASGITransport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


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
