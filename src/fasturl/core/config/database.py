"""Database configuration section."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """Settings for the SQLAlchemy database connection."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    url: str = Field(
        default="sqlite+aiosqlite:///instance/fasturl.db",
        description="SQLAlchemy async database URL.",
    )
    echo: bool = Field(default=False, description="Log all SQL statements emitted by SQLAlchemy.")
