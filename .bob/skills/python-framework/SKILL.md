---
name: python-framework
description: Use when the user wants to adapt a Python project structure to the framework chosen in docs/tech-stack.md — creates framework-specific folders, stub files, entry points, and pyproject.toml dependencies. Requires /framework and /python-init to have been run first.
metadata:
  disable-model-invocation: false
  argument-hint: "[framework]"
---

# Python Framework — Project Structure Adaptation

Adapt the Python project structure to the specific framework recorded in `docs/tech-stack.md`.

This skill runs **after** `/framework` (stack decision) and `/python-init` (project scaffold).
It reads what is already in `src/<package>/`, then adds or adjusts only what the framework
requires — it never deletes or overwrites existing architecture layers.

---

## Step 0 — Check Prerequisites

### 0.1 — Tech stack document

```
glob: docs/tech-stack.md
```

**If not found:**
- Stop immediately and tell the user:
  _"No technology stack document found. Please run `/framework` first — it produces
  `docs/tech-stack.md` which defines the framework to adapt to. Once that document exists,
  come back and run `/python-framework` again."_
- Do not proceed further.

**If found:**
- Read it with `read_file`
- Extract: app framework, ORM/data access choice, testing stack, code quality tools
- Tell the user: _"I found a tech stack for `<domain>` using `<framework>`. I'll adapt the
  project structure to it."_

### 0.2 — Architecture document

```
glob: docs/architecture.md
```

**If found:**
- Read it with `read_file`
- Extract: pattern, organisation style — these determine how framework additions map onto layers
- If not found, continue without it (framework adaptation can proceed without it, but mapping
  notes to architecture layers will be skipped)

### 0.3 — Project scaffold

Inspect the workspace root with `list_files`. A ready scaffold must have:

| Artefact | Required |
|----------|----------|
| `pyproject.toml` | ✅ |
| `src/<package>/` | ✅ |
| `.python-version` | ✅ |
| `uv.lock` | ✅ |

If **any** are missing, stop and tell the user:
_"The project scaffold is not ready. Please run `/python-init <project-name>` first, then
re-invoke `/python-framework`."_

**Project root:** look for `src/<package>/`. If exactly one package exists, use it. If multiple,
ask:

```
ask_followup_question: "Where is the package root?"
suggestion_a: "src/<package>/ (detected)"
suggestion_b: "Enter a custom path"
```

### 0.4 — Framework to apply

Read the `App framework` field from `docs/tech-stack.md`. If it is ambiguous or not set, ask:

```
ask_followup_question: "Which Python framework should I adapt the project structure for?"
suggestion_a: "FastAPI — async REST API"
suggestion_b: "Django — full-stack web with ORM and admin"
suggestion_c: "Flask — lightweight web / API"
suggestion_d: "Celery — distributed task queue / background workers"
```

---

## Step 1 — Apply Framework-Specific Additions

Apply the additions for the chosen framework. Use `write_file` for new files and `apply_diff`
to extend existing ones (e.g. `pyproject.toml`). Never overwrite `__init__.py` files that
already have content.

Each new `__init__.py` must follow the standard header + docstring + `__all__` pattern:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""<one-line description of this layer's responsibility>."""

__all__: list[str] = []
```

---

### `fastapi`

Add or extend:

```
<root>/
├── api/
│   ├── __init__.py
│   ├── routers/
│   │   └── __init__.py     ← one router file per resource/domain
│   ├── schemas/
│   │   └── __init__.py     ← Pydantic request/response models
│   ├── dependencies/
│   │   └── __init__.py     ← FastAPI Depends() factories
│   └── middleware/
│       └── __init__.py     ← custom Starlette middleware
└── main.py                 ← FastAPI app factory
```

`main.py` stub:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI()

# Register routers here:
# from <package>.api.routers import some_router
# app.include_router(some_router.router, prefix="/some", tags=["some"])
```

Add to `pyproject.toml` dependencies if not present:
```
uv add fastapi uvicorn[standard]
```

**Architecture layer mapping** (if `docs/architecture.md` defines ddd or hexagonal):
- `api/routers/` → `interfaces/api/` driving adapters
- `api/schemas/` → request/response DTOs (separate from domain entities)
- `api/dependencies/` → application service injection via `Depends()`

---

### `django`

Django has strong conventions. Adapt the architecture layers into Django's app model:

```
<root>/                         ← becomes a Django project package
├── settings/
│   ├── __init__.py
│   ├── base.py                 ← shared settings
│   ├── development.py          ← overrides for dev
│   └── production.py           ← overrides for prod
├── urls.py                     ← root URL configuration
├── wsgi.py
├── asgi.py
└── apps/                       ← one Django app per bounded context / resource
    └── <first_app>/
        ├── __init__.py
        ├── models.py           ← Django ORM models
        ├── views.py            ← HTTP handlers
        ├── serializers.py      ← DRF serializers
        ├── urls.py
        ├── admin.py
        └── migrations/
            └── __init__.py
```

`manage.py` stub at project root (one level above `src/`):

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "<package>.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

Add dependencies:
```
uv add django
uv add djangorestframework   # if REST API is needed
```

**Architecture layer mapping** (if `docs/architecture.md` defines ddd or hexagonal):
- `apps/<name>/models.py` → `domain/entities/`
- `apps/<name>/views.py` → `interfaces/api/`
- `apps/<name>/serializers.py` → `api/schemas/`
- `apps/<name>/migrations/` → `infrastructure/persistence/`

---

### `flask`

```
<root>/
├── api/
│   ├── __init__.py
│   ├── blueprints/
│   │   └── __init__.py     ← one Blueprint per resource/domain
│   └── schemas/
│       └── __init__.py     ← marshmallow or pydantic schemas
└── main.py                 ← Flask app factory
```

`main.py` stub:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Flask application entry point."""

from flask import Flask


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)

    # Register blueprints here:
    # from <package>.api.blueprints import some_blueprint
    # app.register_blueprint(some_blueprint.bp, url_prefix="/some")

    return app


app = create_app()
```

Add dependency:
```
uv add flask
```

---

### `celery`

```
<root>/
├── tasks/
│   └── __init__.py         ← Celery task definitions
├── workers/
│   └── __init__.py         ← worker configuration and entrypoints
├── schedules/
│   └── __init__.py         ← beat schedules (periodic tasks)
└── celery_app.py           ← Celery app factory
```

`celery_app.py` stub:

```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Celery application factory."""

from celery import Celery

celery_app = Celery(__name__)

# Configuration loaded from core.config:
# celery_app.conf.broker_url = settings.celery.broker_url
# celery_app.conf.result_backend = settings.celery.result_backend

# Auto-discover tasks:
# celery_app.autodiscover_tasks(["<package>.tasks"])
```

Add dependency:
```
uv add celery
```

---

### `typer` (CLI)

> For CLI projects, `/python-cli` is the primary skill. Use this only to wire Typer into an
> existing project scaffold that was set up via `/python-init` without CLI scaffolding.

```
<root>/
├── commands/
│   ├── __init__.py
│   └── base.py             ← marker ABC
└── cli.py                  ← Typer app wiring
```

Add entry point to `pyproject.toml`:
```toml
[project.scripts]
<cli-name> = "<package>.cli:main"
```

Add dependency:
```
uv add typer
```

---

## Step 2 — Report

Show:
1. Framework applied and version added to `pyproject.toml`
2. Files created or modified (with paths)
3. How the framework additions map onto the existing architecture layers (from `docs/architecture.md`)

Then prompt for next steps:

```
ask_followup_question: "What would you like to do next?"
suggestion_a: "Generate the configuration module — run /python-config"
suggestion_b: "Design the database schema — run /db-designer"
suggestion_c: "Design the CLI interface — run /cli-design"
suggestion_d: "The project setup is complete for now"
```
