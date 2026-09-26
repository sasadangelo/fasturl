"""URL inspector configuration section."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InspectorConfig(BaseSettings):
    """Settings for the outbound URL inspector / resolver."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    timeout_seconds: float = Field(default=5.0, description="HTTP request timeout in seconds.")
    max_redirects: int = Field(default=3, description="Maximum number of redirects to follow.")
