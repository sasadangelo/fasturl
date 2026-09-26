"""Logging configuration section."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogConfig(BaseSettings):
    """Settings for the application logger (Loguru-compatible)."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    level: str = Field(default="INFO", description="Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).")
    console: bool = Field(default=True, description="Write log output to stdout.")
    file: str = Field(default="logs/fasturl.log", description="Path to the rotating log file.")
    rotation: str = Field(default="10 MB", description="Rotate the log file when it reaches this size.")
    retention: str = Field(default="7 days", description="Delete rotated log files older than this period.")
    compression: str = Field(default="zip", description="Compression format applied to rotated log files.")
