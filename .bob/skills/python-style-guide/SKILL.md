---
name: python-style-guide
description: Python coding style and conventions for this project. Use whenever writing, reviewing, editing, or reviewing Python code for this project — covers type hints, import ordering, docstrings, naming conventions, formatting (black/isort/flake8), error handling, logging, and module/file structure. Apply these conventions automatically whenever generating or modifying Python code in this codebase, even if the user doesn't explicitly ask for "style compliant" or "PEP 8" code.
---

# Python Style Guide

Coding standards and conventions for this project. These extend PEP 8 with project-specific rules — where this guide differs from vanilla PEP 8 (line length, type hints, docstring style), follow this guide.

## Quick reference

| Aspect | Rule |
|---|---|
| Line length | 120 chars max |
| Python version | 3.12+ minimum |
| Type hints | Modern syntax (`list[str]`, `X \| None`), always on params + return |
| Formatter / Linter | ruff (default config, line length 120) |
| Docstrings | Google style |
| Dependency manager | uv |

## Type hints

Always use modern (3.10+) syntax — never import from `typing` for things Python now supports natively.

✅ Do:
```python
def process_data(items: list[str]) -> dict[str, int]:
    pass

def get_user(user_id: int | None) -> tuple[str, int]:
    pass

def merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    pass
```

❌ Don't:
```python
from typing import List, Dict, Tuple, Union, Optional

def process_data(items: List[str]) -> Dict[str, int]:
    pass

def get_user(user_id: Optional[int]) -> Tuple[str, int]:
    pass
```

Guidelines:
- Use `list`, `dict`, `tuple`, `set` instead of `List`, `Dict`, `Tuple`, `Set`.
- Use `|` for unions instead of `Union`; use `X | None` instead of `Optional[X]`.
- Always include a return type hint — use `-> None` for functions that return nothing.
- Use `Any` (from `typing`) only when the type is genuinely dynamic; prefer explicit types otherwise.
- Use `Sequence` for read-only sequence parameters when appropriate.

Project example:
```python
def _merge_record_with_metadata(
    self, record_dto: RecordDTO, metadata_map: dict[tuple[int | None, str], MetadataDTO]
) -> RecordWithMetadata:
    """Merge a record with its associated metadata."""
    pass
```

## Imports

Order follows ruff's default isort rules. Sections:

1. `__future__` imports
2. Standard library
3. Third-party
4. First-party (project)
5. Local folder

```python
# Standard library
import os
from datetime import datetime
from typing import Any, Sequence

# Third-party
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Row

# Project imports
from core.libraries.log import setup_logger
from core.database.services.db_service import DBService
from api.dtos import RecordsResponse, RecordWithMetadata
```

## Formatting & linting

Automated tools enforce formatting — don't hand-format against them:
- **ruff** — single tool for both formatting and linting, with this config:
  ```toml
  [tool.ruff]
  line-length = 120
  ```
  All other settings are ruff defaults. Ruff replaces black, isort, and flake8.

Pre-commit hooks run ruff and `detect-secrets` (secret-scanning). All code must pass these before committing.

## Docstrings

Use Google-style docstrings:

```python
def process_report(self, df: pd.DataFrame, scan_job_id: int) -> pd.DataFrame:
    """
    Process and evaluate a report dataframe.

    Args:
        df: Input dataframe containing report data
        scan_job_id: ID of the scan job

    Returns:
        Processed dataframe with evaluation results
    """
    pass
```

Every module needs a module-level docstring, preceded by the standard copyright header:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""
Service for retrieving records from the database
"""
```

## Naming conventions

| Kind | Convention | Example |
|---|---|---|
| Classes | PascalCase | `RecordsService`, `WorkflowService` |
| Functions / methods | snake_case | `process_report`, `get_job_type` |
| Private methods / attributes | snake_case, `_` prefix | `_logger`, `_private_method` |
| Constants | UPPER_SNAKE_CASE | `ENV_FILE`, `MAX_RETRIES` |
| Variables | snake_case | `job_id`, `temp_dir` |

## Class structure

```python
class MyService:
    """Service description."""

    def __init__(self) -> None:
        self._logger = setup_logger(name=self.__class__.__name__)
        self._private_attribute = value

    def public_method(self, param: str) -> int:
        """Public method description."""
        pass

    def _private_method(self) -> None:
        """Private method description."""
        pass
```

## Error handling & logging

Catch specific exceptions, log before re-raising:

```python
try:
    result = risky_operation()
except SpecificException as e:
    self._logger.error(f"Operation failed: {e}")
    raise
```

Use the project's logger setup rather than `print` or ad-hoc logging:

```python
from core.libraries.log import setup_logger

class MyClass:
    def __init__(self) -> None:
        self._logger = setup_logger(self.__class__.__name__)

    def process(self) -> None:
        self._logger.info("Processing started")
        self._logger.error("An error occurred")
```

## String formatting

Prefer f-strings; avoid `.format()` and `%` formatting.

```python
# Good
message = f"Processing {count} items for user {user_id}"

# Avoid
message = "Processing {} items for user {}".format(count, user_id)
message = "Processing %s items for user %s" % (count, user_id)
```

## File organization

```
module_name/
├── __init__.py          # Public API exports
├── dtos/                # Data Transfer Objects
│   ├── __init__.py
│   └── model.py
├── services/            # Business logic
│   ├── __init__.py
│   └── service.py
└── clients/             # External integrations
    ├── __init__.py
    └── client.py
```

`__init__.py` files always use explicit `__all__` exports:

```python
from .model import Model1, Model2
from .service import Service1

__all__ = [
    "Model1",
    "Model2",
    "Service1",
]
```

## Other conventions

- Minimum Python version: 3.12. Use modern features (structural pattern matching, etc.) when they improve clarity.
- Use `mypy` for static type checking; prefer explicit types over implicit `Any`.
- Manage dependencies with `uv`; keep them up to date; separate production and dev dependencies in `pyproject.toml`.
- Prioritize code clarity over cleverness.
