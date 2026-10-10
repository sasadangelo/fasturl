# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for the startup configuration summary (``python -m fasturl.core.config``)."""

from __future__ import annotations

from collections.abc import Mapping
from unittest.mock import patch

from fasturl.core.config import Settings
from fasturl.core.config.__main__ import summary
from fasturl.core.config.database import DatabaseConfig


def _settings(database: Mapping[str, object]) -> Settings:
    """Return a Settings copy whose database section is validated from ``database``."""
    custom_settings = Settings()
    custom_settings.database = DatabaseConfig.model_validate(database)
    return custom_settings


def test_summary_sqlite_has_no_pool_line() -> None:
    """With SQLite the summary shows the database file and no pool settings."""
    with patch("fasturl.core.config.__main__.settings", _settings({"sqlite": {"path": "instance/x.db"}})):
        text = summary(workers=1)

    assert "1 worker(s)" in text
    assert "Database: SQLite — sqlite+aiosqlite:///instance/x.db" in text
    assert "Pool:" not in text


def test_summary_postgres_masks_password_and_totals_connections() -> None:
    """With PostgreSQL the password is masked and total connections = workers * per-worker pool."""
    database = {
        "postgresql": {
            "host": "db.local",
            "password": "topsecret",  # pragma: allowlist secret
            "pool_size": 15,
            "max_overflow": 5,
        }
    }
    with patch("fasturl.core.config.__main__.settings", _settings(database)):
        text = summary(workers=4)

    assert "topsecret" not in text
    assert "Database: PostgreSQL — postgresql+asyncpg://fasturl_user:***@db.local:5432/fasturl_db" in text
    assert "max 80 connections" in text
