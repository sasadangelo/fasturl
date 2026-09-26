"""Root Settings class — single source of truth for all application configuration.

Usage
-----
Import the module-level singleton in any module that needs configuration::

    from fasturl.core.config import settings

    print(settings.app.host)
    print(settings.database.url)

Never instantiate ``Settings()`` anywhere else.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

try:
    from pydantic_settings import YamlConfigSettingsSource
except ImportError:  # pydantic-settings < 2.3
    YamlConfigSettingsSource = None  # type: ignore[assignment,misc]

from fasturl.core.config.app import AppConfig
from fasturl.core.config.database import DatabaseConfig
from fasturl.core.config.inspector import InspectorConfig
from fasturl.core.config.log import LogConfig


class Settings(BaseSettings):
    """Merged application settings loaded from *config.yaml* and *.env*."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig, description="HTTP server and application settings.")
    database: DatabaseConfig = Field(default_factory=DatabaseConfig, description="Database connection settings.")
    log: LogConfig = Field(default_factory=LogConfig, description="Logger settings.")
    inspector: InspectorConfig = Field(default_factory=InspectorConfig, description="URL inspector settings.")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
        **kwargs: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load from env vars first, then YAML (env vars take precedence)."""
        sources: tuple[PydanticBaseSettingsSource, ...] = (init_settings, env_settings, dotenv_settings)
        if YamlConfigSettingsSource is not None:
            sources += (YamlConfigSettingsSource(settings_cls, yaml_file="config.yaml"),)
        return sources


# ---------------------------------------------------------------------------
# Module-level singleton — import this, never call Settings() again.
# ---------------------------------------------------------------------------
settings: Settings = Settings()
