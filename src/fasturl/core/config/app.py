"""Application server configuration section."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Settings for the HTTP server and application behaviour."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    host: str = Field(default="127.0.0.1", description="Bind address for the HTTP server.")
    port: int = Field(default=8000, description="TCP port the HTTP server listens on.")
    base_url: str = Field(default="http://localhost:8000", description="Public base URL of the application.")
    debug: bool = Field(default=False, description="Enable debug mode (verbose errors, auto-reload).")
    code_length: int = Field(default=7, description="Length of generated short-URL codes.")
