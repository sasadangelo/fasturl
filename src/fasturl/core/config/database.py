"""Database configuration section.

Exactly one backend sub-section must be active in ``config.yaml`` (comment out the other)::

    database:
      echo: false
      # sqlite:
      #   path: "instance/fasturl.db"
      postgresql:
        host: "127.0.0.1"
        ...

When no backend section is configured, SQLite with default settings is used.
The PostgreSQL password is a secret: set it in ``.env`` as ``DATABASE__POSTGRESQL__PASSWORD``.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class SQLiteDatabaseConfig(BaseModel):
    """Settings for the SQLite backend (single worker only)."""

    path: str = Field(default="instance/fasturl.db", description="SQLite database file path.")

    @property
    def url(self) -> URL:
        """SQLAlchemy async connection URL for the database file."""
        return URL.create(drivername="sqlite+aiosqlite", database=self.path)


class PostgreSQLDatabaseConfig(BaseModel):
    """Settings for the PostgreSQL backend, including the per-worker connection pool."""

    host: str = Field(default="127.0.0.1", description="PostgreSQL server host.")
    port: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL server port.")
    name: str = Field(default="fasturl_db", description="PostgreSQL database name.")
    user: str = Field(default="fasturl_user", description="PostgreSQL user.")
    password: SecretStr = Field(default=SecretStr(""), description="PostgreSQL password (from .env).")
    pool_size: int = Field(default=10, ge=1, description="Connection pool size per worker.")
    max_overflow: int = Field(default=0, ge=0, description="Max overflow connections per worker.")
    pool_timeout: int = Field(default=30, ge=1, description="Pool checkout timeout in seconds.")
    pool_recycle: int = Field(default=1800, ge=-1, description="Recycle connections after N seconds.")

    @property
    def url(self) -> URL:
        """SQLAlchemy async connection URL built from the connection fields."""
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.name,
        )


class DatabaseConfig(BaseSettings):
    """Settings for the SQLAlchemy database connection."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    echo: bool = Field(default=False, description="Log all SQL statements emitted by SQLAlchemy.")
    sqlite: SQLiteDatabaseConfig | None = Field(default=None, description="SQLite backend settings.")
    postgresql: PostgreSQLDatabaseConfig | None = Field(default=None, description="PostgreSQL backend settings.")

    @model_validator(mode="after")
    def _select_backend(self) -> DatabaseConfig:
        """Ensure exactly one backend is active, defaulting to SQLite.

        A ``postgresql`` section that only carries the password (set in ``.env``)
        does not activate PostgreSQL, so the secret can stay in ``.env`` while SQLite is used.
        """
        if self.postgresql is not None and not (self.postgresql.model_fields_set - {"password"}):
            self.postgresql = None
        if self.sqlite is not None and self.postgresql is not None:
            raise ValueError("configure only one database backend: comment out either 'sqlite' or 'postgresql'")
        if self.postgresql is not None and not self.postgresql.password.get_secret_value():
            raise ValueError("PostgreSQL password is required: set DATABASE__POSTGRESQL__PASSWORD in .env")
        if self.postgresql is None and self.sqlite is None:
            self.sqlite = SQLiteDatabaseConfig()
        return self

    @property
    def backend(self) -> Literal["sqlite", "postgresql"]:
        """Name of the active backend."""
        return "postgresql" if self.postgresql is not None else "sqlite"

    @property
    def url(self) -> URL:
        """SQLAlchemy async connection URL of the active backend."""
        if self.postgresql is not None:
            return self.postgresql.url
        return (self.sqlite or SQLiteDatabaseConfig()).url
