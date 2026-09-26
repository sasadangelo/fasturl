---
name: python-log
description: Use when the user types /add-python-log or asks to add logging to a Python project using Loguru. Generates core/log.py with LoggerManager, updates config.yaml with the log section, and shows where and how to add logging in each architecture layer.
metadata:
  disable-model-invocation: true
  argument-hint: "[config.yaml]"
---

# Python Log

Add a production-ready Loguru logging setup to a Python project.

This skill generates `core/log.py`, updates `config.yaml` with the `log` section, and guides the
user on where and how to log in each architecture layer.

---

## Step 1 — Locate the project

Look for `src/<package>/core/` in the workspace. If exactly one package exists under `src/`, use it.
If none exists or there are multiple, ask:

```
ask_followup_question: "Where is the package root (e.g. src/my_package)?"
```

Also check whether `config.yaml` already exists (to know whether to create or extend it).

---

## Step 2 — Detect the architecture layer order

Look at the top-level folders under `src/<package>/` to infer the architecture. Use this priority
for logging guidance in Step 7:

| Folders found                                | Architecture         | Layers to log (most → least important)    |
| -------------------------------------------- | -------------------- | ----------------------------------------- |
| `services/`, `api/` or `repositories/`       | `layered`            | services → api/controllers → repositories |
| `application/`, `domain/`, `infrastructure/` | `hexagonal` or `ddd` | application → interfaces → infrastructure |
| `consumers/`, `processors/`                  | `event-driven`       | processors → consumers → producers        |
| `steps/`, `pipelines/`                       | `pipeline`           | steps → pipelines → io                    |

If no recognizable structure is found, use `layered` as default and note the assumption.

---

## Step 3 — Generate `core/log.py`

Write `src/<package>/core/log.py` with the full implementation below.

### Log format

Two formats are used:

- **Application logs** (from classes using `LoggerManager.get_logger`): include thread name, class,
  function — the full context needed to trace a request through the system.
- **Intercepted logs** (from Flask, Werkzeug, SQLAlchemy, uvicorn, etc.): same fields, but the
  `name` comes from the standard library record rather than `extra[name]`.

Both formats expose these fields in every line:

```
timestamp | thread | level | class/module | function | message
```

Example output:

```
2025-01-15 10:23:45.123 | MainThread | INFO  | RaceService | create_race | Race 'Milano Marathon' created with ID 42
2025-01-15 10:23:45.456 | MainThread | ERROR | RaceService | create_race | Failed to create race 'Milano Marathon': ...
```

### Full `core/log.py`

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""
Centralized logging setup using Loguru.

Call setup_logging() once at application startup, before any other component.
All modules obtain a bound logger via LoggerManager.get_logger(name).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import FrameType

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
    """
    Centralized Loguru logger manager.

    Initialized once at startup via setup_logging(). Individual classes obtain
    a bound logger via LoggerManager.get_logger(name).
    """

    def __init__(
        self,
        level: str = "INFO",
        console: bool = True,
        file: str = "logs/app.log",
        rotation: str = "10 MB",
        retention: str = "7 days",
        compression: str = "zip",
    ) -> None:
        """
        Initialize the logger manager.

        Args:
            level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            console: Whether to log to stdout.
            file: Path to the log file (e.g. "logs/app.log").
            rotation: When to rotate the log file (e.g. "10 MB", "1 day").
            retention: How long to keep rotated files (e.g. "7 days").
            compression: Compression format for rotated files (e.g. "zip").
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

        def format_record(record: dict) -> str:
            format_map: dict[bool, str] = {
                True: APP_LOG_FORMAT,
                False: INTERCEPTED_LOG_FORMAT,
            }
            return format_map["name" in record["extra"]]

        if self.console:
            logger.add(
                sink=sys.stdout,
                format=format_record,
                level=self.level,
                colorize=True,
            )

        log_path = Path(self.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            sink=self.file,
            format=format_record,
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
    def get_logger(name: str) -> logger:
        """
        Return a logger bound to the given name (class or module).

        Args:
            name: Identifier shown in the log line (typically self.__class__.__name__).

        Returns:
            A Loguru logger bound to the given name.
        """
        return logger.bind(name=name)


def setup_logging(
    level: str = "INFO",
    console: bool = True,
    file: str = "logs/app.log",
    rotation: str = "10 MB",
    retention: str = "7 days",
    compression: str = "zip",
) -> LoggerManager:
    """
    Initialize the application logging system.

    Call this once at startup, after settings are loaded and before any other component.

    Args:
        level: Minimum log level.
        console: Whether to log to stdout.
        file: Path to the log file.
        rotation: Log file rotation policy.
        retention: Log file retention policy.
        compression: Compression format for rotated files.

    Returns:
        The configured LoggerManager instance.
    """
    return LoggerManager(
        level=level,
        console=console,
        file=file,
        rotation=rotation,
        retention=retention,
        compression=compression,
    )
```

---

## Step 4 — Update `config.yaml`

If `config.yaml` exists, add the `log` section using `apply_diff`.
If it does not exist, create it with `write_file`.

The `log` section must always include a `file` path — file logging is always enabled.
Derive the log filename from the package name (e.g. package `investor` → `logs/investor.log`):

```yaml
log:
  level: "INFO"
  console: true
  file: "logs/<package>.log"
  rotation: "10 MB"
  retention: "7 days"
  compression: "zip"
```

---

## Step 5 — Update `pyproject.toml`

Add `"loguru>=0.7"` to the project dependencies if not already present.

---

## Step 6 — Show how to wire logging at startup

Show the user where to call `setup_logging()` in their entry point (`main.py` or equivalent).
The call must happen **after** `settings` is loaded and **before** any other component.

```python
from core.config import settings
from core.log import setup_logging

setup_logging(
    level=settings.log.level,
    console=settings.log.console,
    file=settings.log.file,
    rotation=settings.log.rotation,
    retention=settings.log.retention,
    compression=settings.log.compression,
)
```

---

## Step 7 — Show how to log in each layer

### The golden rule

Logs must **tell a story** — each line is an **event** with a clear subject, action, and outcome.
Write logs as if they were entries in an operations journal: what happened, to what, and with what
result. Never log raw state. Never log entry/exit of every function.

```python
# ✅ Event — tells a story
self._logger.info(f"Race '{race.name}' created with ID {result.id}")
self._logger.warning(f"Race '{race_id}' not found — returning 404")
self._logger.error(f"Failed to delete race '{race_id}': {e}")

# ❌ State dump — tells nothing
self._logger.debug(f"race = {race}")
self._logger.info("entering create_race")
self._logger.info("done")
```

### Log level guide

| Level      | When to use                                                               |
| ---------- | ------------------------------------------------------------------------- |
| `DEBUG`    | Detailed internal flow — only during development                          |
| `INFO`     | Normal business events: created, updated, deleted, started, completed     |
| `WARNING`  | Expected but notable: not found, retrying, fallback used                  |
| `ERROR`    | Failure affecting one request/operation but not the whole system          |
| `CRITICAL` | Failure affecting the whole system (startup failure, unrecoverable state) |

### Getting a logger in any class

```python
from core.log import LoggerManager

class MyService:
    def __init__(self) -> None:
        self._logger = LoggerManager.get_logger(self.__class__.__name__)
```

Always use `self.__class__.__name__` — it appears in the `class` column of every log line,
enabling instant filtering by component.

### Layer-by-layer guidance

Show guidance for the layers detected in Step 2. Always present them in priority order
(most important → least important).

#### Service / Application layer ← **log the most here**

Business logic lives here. Log every significant business event and every failure.

```python
class RaceService:
    def __init__(self) -> None:
        self._logger = LoggerManager.get_logger(self.__class__.__name__)

    def create_race(self, race: Race) -> Race:
        """Create a new race."""
        try:
            result = self._repository.save(race)
            self._logger.info(f"Race '{race.name}' created with ID {result.id}")
            return result
        except SQLAlchemyError as e:
            self._logger.error(f"Failed to create race '{race.name}': {e}")
            raise

    def delete_race(self, race_id: int) -> None:
        """Delete a race by ID."""
        race = self._repository.find_by_id(race_id)
        if not race:
            self._logger.warning(f"Race '{race_id}' not found — skipping delete")
            raise RaceNotFoundError(race_id)
        self._repository.delete(race_id)
        self._logger.info(f"Race '{race_id}' deleted")
```

Log: creation, update, deletion, workflow transitions, retry attempts, external call outcomes.

#### API / Controller / Interface layer ← **log errors and unexpected paths only**

Log validation failures and unexpected exceptions. Do **not** duplicate what the service logs.

```python
class RaceController:
    def __init__(self) -> None:
        self._logger = LoggerManager.get_logger(self.__class__.__name__)

    def delete_race(self, race_id: int) -> WebResponse:
        """Handle DELETE /races/{race_id}."""
        try:
            self._service.delete_race(race_id)
            return ok()
        except RaceNotFoundError:
            # service already logged a warning — no need to log again
            return not_found()
        except Exception as e:
            self._logger.error(f"Unexpected error deleting race '{race_id}': {e}")
            return internal_error()
```

#### Repository / Infrastructure / Persistence layer ← **log sparingly, DEBUG only**

Log only at DEBUG for query-level details. The service layer owns the business outcome — the
repository only logs the mechanical operation when it aids debugging.

```python
class RaceRepository:
    def __init__(self) -> None:
        self._logger = LoggerManager.get_logger(self.__class__.__name__)

    def find_by_id(self, race_id: int) -> Race | None:
        """Find a race by ID."""
        self._logger.debug(f"Querying race with ID {race_id}")
        return self._session.get(Race, race_id)
```

#### Where NOT to log

- Domain entities and value objects (pure data, no side effects)
- SQLAlchemy / ORM model definitions
- DTOs and schema classes
- Simple utility / helper functions with no external effects

---

## Step 8 — Report to the user

Summarise:

- Files created or modified (with clickable paths).
- The log format fields: `timestamp | thread | level | class | function | message`.
- The log file path derived from the package name.
- The architecture layers detected and their logging priority.
- Reminder: call `setup_logging()` at startup **after** `settings` is loaded.
- Next step if `config.yaml` was not yet processed by `/add-python-config`:
  ```
  /add-python-config config.yaml   — generate the full Pydantic Settings module
  ```
