"""Centralized logging setup using Loguru.

Call ``setup_logging()`` once at application startup, before any other component.
All modules obtain a bound logger via ``LoggerManager.get_logger(name)``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import FrameType
from typing import Any

from loguru import logger

APP_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<cyan>{thread.name}</cyan> | "
    "<level>{level}</level> | "
    "<cyan>{extra[name]}</cyan> | "
    "<cyan>{function}</cyan> | "
    "<level>{message}</level>\n{exception}"
)

INTERCEPTED_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<cyan>{thread.name}</cyan> | "
    "<level>{level}</level> | "
    "<cyan>{name}</cyan> | "
    "<cyan>{function}</cyan> | "
    "<level>{message}</level>\n{exception}"
)


class InterceptHandler(logging.Handler):
    """Redirect standard library logging to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record via Loguru."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class LoggerManager:
    """Centralized Loguru logger manager.

    Initialized once at startup via ``setup_logging()``. Individual classes obtain
    a bound logger via ``LoggerManager.get_logger(name)``.
    """

    def __init__(
        self,
        level: str = "INFO",
        console: bool = True,
        file: str = "logs/fasturl.log",
        rotation: str = "10 MB",
        retention: str = "7 days",
        compression: str = "zip",
    ) -> None:
        """Initialize the logger manager.

        Args:
            level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            console: Whether to log to stdout.
            file: Path to the log file (e.g. ``logs/fasturl.log``).
            rotation: When to rotate the log file (e.g. ``"10 MB"``, ``"1 day"``).
            retention: How long to keep rotated files (e.g. ``"7 days"``).
            compression: Compression format for rotated files (e.g. ``"zip"``).
        """
        self.level = level.upper()
        self.console = console
        self.file = file
        self.rotation = rotation
        self.retention = retention
        self.compression = compression

        logger.remove()
        self._configure_logger()
        self._intercept_standard_logging()

    def _configure_logger(self) -> None:
        """Configure Loguru handlers based on settings."""

        def format_record(record: dict) -> str:  # type: ignore[type-arg]
            format_map: dict[bool, str] = {
                True: APP_LOG_FORMAT,
                False: INTERCEPTED_LOG_FORMAT,
            }
            return format_map["name" in record["extra"]]

        if self.console:
            logger.add(
                sink=sys.stdout,
                format=format_record,  # type: ignore[arg-type]
                level=self.level,
                colorize=True,
            )

        log_path = Path(self.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            sink=self.file,
            format=format_record,  # type: ignore[arg-type]
            level=self.level,
            rotation=self.rotation,
            retention=self.retention,
            compression=self.compression,
            enqueue=True,
        )

    def _intercept_standard_logging(self) -> None:
        """Intercept standard library logging and redirect to Loguru."""
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
        for name in ["werkzeug", "flask.app", "uvicorn", "uvicorn.access", "sqlalchemy.engine"]:
            log = logging.getLogger(name=name)
            log.handlers = [InterceptHandler()]
            log.propagate = False

    @staticmethod
    def get_logger(name: str) -> Any:
        """Return a logger bound to the given name (class or module).

        Args:
            name: Identifier shown in the log line (typically ``self.__class__.__name__``).

        Returns:
            A Loguru logger bound to the given name.
        """
        return logger.bind(name=name)


def setup_logging(
    level: str = "INFO",
    console: bool = True,
    file: str = "logs/fasturl.log",
    rotation: str = "10 MB",
    retention: str = "7 days",
    compression: str = "zip",
) -> LoggerManager:
    """Initialize the application logging system.

    Call this once at startup, after settings are loaded and before any other component.

    Args:
        level: Minimum log level.
        console: Whether to log to stdout.
        file: Path to the log file.
        rotation: Log file rotation policy.
        retention: Log file retention policy.
        compression: Compression format for rotated files.

    Returns:
        The configured ``LoggerManager`` instance.
    """
    return LoggerManager(
        level=level,
        console=console,
        file=file,
        rotation=rotation,
        retention=retention,
        compression=compression,
    )
