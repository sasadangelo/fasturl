# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for database engine and configuration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

import fasturl.core.database as db_module
from fasturl.core.config import Settings
from fasturl.core.config.database import DatabaseConfig, PostgreSQLDatabaseConfig, SQLiteDatabaseConfig
from fasturl.core.database import close_db, get_db, init_db


@pytest.mark.asyncio
async def test_init_db_sqlite() -> None:
    """Test init_db creates engine for SQLite without pooling arguments."""
    with patch("fasturl.core.database.create_async_engine") as mock_create_engine:
        custom_settings = Settings()
        custom_settings.database.sqlite = SQLiteDatabaseConfig(path="instance/fasturl.db")
        custom_settings.database.postgresql = None

        with patch("fasturl.core.database.settings", custom_settings):
            mock_engine = MagicMock()
            mock_engine.begin.return_value.__aenter__ = AsyncMock()
            mock_engine.begin.return_value.__aexit__ = AsyncMock()
            mock_engine.dispose = AsyncMock()
            mock_create_engine.return_value = mock_engine

            await init_db()

            mock_create_engine.assert_called_once()
            _, kwargs = mock_create_engine.call_args
            assert "pool_size" not in kwargs
            assert kwargs.get("echo") is False

            await close_db()


@pytest.mark.asyncio
async def test_init_db_postgres() -> None:
    """Test init_db creates engine for PostgreSQL with pool settings and pre_ping."""
    with patch("fasturl.core.database.create_async_engine") as mock_create_engine:
        custom_settings = Settings()
        custom_settings.database.sqlite = None
        custom_settings.database.postgresql = PostgreSQLDatabaseConfig(
            password=SecretStr("secret"), pool_size=15, max_overflow=5
        )

        with patch("fasturl.core.database.settings", custom_settings):
            mock_engine = MagicMock()
            mock_engine.begin.return_value.__aenter__ = AsyncMock()
            mock_engine.begin.return_value.__aexit__ = AsyncMock()
            mock_engine.dispose = AsyncMock()
            mock_create_engine.return_value = mock_engine

            await init_db()

            mock_create_engine.assert_called_once()
            _, kwargs = mock_create_engine.call_args
            assert kwargs.get("pool_size") == 15
            assert kwargs.get("max_overflow") == 5
            assert kwargs.get("pool_pre_ping") is True

            await close_db()


def test_database_defaults_to_sqlite() -> None:
    """With no backend section configured, SQLite with default settings is used."""
    config = DatabaseConfig()

    assert config.backend == "sqlite"
    assert config.url.render_as_string() == "sqlite+aiosqlite:///instance/fasturl.db"


def test_database_url_sqlite() -> None:
    """The SQLite URL is built from the configured file path."""
    config = DatabaseConfig.model_validate({"sqlite": {"path": "instance/test.db"}})

    assert config.backend == "sqlite"
    assert config.url.render_as_string() == "sqlite+aiosqlite:///instance/test.db"


def test_database_url_postgres() -> None:
    """The PostgreSQL URL is built from host, port, name, user and password."""
    config = DatabaseConfig.model_validate(
        {
            "postgresql": {
                "host": "db.local",
                "port": 5433,
                "name": "mydb",
                "user": "me",
                "password": "p@ss",  # pragma: allowlist secret
            }
        }
    )

    assert config.backend == "postgresql"
    expected = "postgresql+asyncpg://me:p%40ss@db.local:5433/mydb"  # pragma: allowlist secret
    assert config.url.render_as_string(hide_password=False) == expected
    assert "p@ss" not in config.url.render_as_string(hide_password=True)


def test_database_postgres_requires_password() -> None:
    """An active PostgreSQL section without a password fails at validation time."""
    with pytest.raises(ValidationError, match="DATABASE__POSTGRESQL__PASSWORD"):
        DatabaseConfig.model_validate({"postgresql": {"host": "db.local"}})


def test_database_rejects_both_backends() -> None:
    """Configuring both SQLite and PostgreSQL is an error."""
    with pytest.raises(ValidationError, match="only one database backend"):
        DatabaseConfig.model_validate(
            {
                "sqlite": {"path": "x.db"},
                "postgresql": {"host": "db.local", "password": "secret"},  # pragma: allowlist secret
            }
        )


def test_database_password_only_does_not_activate_postgres() -> None:
    """A password from .env alone does not activate PostgreSQL when SQLite is configured."""
    config = DatabaseConfig.model_validate({"sqlite": {"path": "x.db"}, "postgresql": {"password": "secret"}})

    assert config.backend == "sqlite"
    assert config.postgresql is None


@pytest.mark.asyncio
async def test_get_db_uninitialised_raises_error() -> None:
    """Calling get_db when factory is None raises RuntimeError."""
    db_module._session_factory = None

    with pytest.raises(RuntimeError, match="Database not initialised"):
        gen = get_db()
        await anext(gen)


@pytest.mark.asyncio
async def test_get_db_yields_session_and_handles_exception() -> None:
    """Test get_db session rollback and close on exception."""
    mock_session = AsyncMock(spec=AsyncSession)

    class MockSessionFactory:
        def __call__(self) -> AsyncMock:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = mock_session
            ctx.__aexit__.return_value = None
            return ctx

    db_module._session_factory = MockSessionFactory()  # type: ignore[assignment]

    gen = cast(AsyncGenerator[AsyncSession, None], get_db())
    session = await anext(gen)
    assert session is mock_session

    with pytest.raises(ValueError, match="Test error"):
        await gen.athrow(ValueError("Test error"))

    mock_session.rollback.assert_awaited_once()
    mock_session.close.assert_awaited_once()

    db_module._session_factory = None
