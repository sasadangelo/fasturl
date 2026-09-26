---
name: python-cli
description: >
  Use when the user wants to implement a Python CLI application.
  Activated by /python-cli. Requires /cli-design to have been run first (reads docs/cli-design.md).
  Implements the CLI using Typer + the Command Pattern.
metadata:
  argument-hint: "[project description]"
---

# Python CLI — Implementation Guide

Implement a CLI from the specification in `docs/cli-design.md` using **Typer** and the
**Command Pattern**.

---

## Phase 0 — Check Prerequisites

### Step 0.1 — CLI design document

```
glob: docs/cli-design.md
```

**If not found:**
- Stop immediately and tell the user:
  _"No CLI design found. Please run `/cli-design` first — it produces `docs/cli-design.md`
  which this skill uses as implementation input. Once that document exists, come back and
  run `/python-cli` again."_
- Do not proceed further.

**If found:**
- Read the file with `read_file`
- Extract: CLI binary name, resources, command table, usage examples, configuration convention
- Tell the user: _"I found a CLI design for `<name>`. I'll implement its `<N>` resources and
  `<M>` commands."_

### Step 0.2 — Scaffold readiness

Inspect the workspace root with `list_files`. A ready scaffold must have:

| Artefact | Required |
|----------|----------|
| `pyproject.toml` | ✅ |
| `src/<package>/` | ✅ |
| `.python-version` | ✅ |
| `uv.lock` | ✅ |

If **any** of these are missing, stop and tell the user:
_"The project scaffold is not ready. Please run `/python-init <project-name>` first, then
re-invoke `/python-cli`."_

### Step 0.3 — Existing code detection

1. Read `pyproject.toml` — understand existing dependencies and entry points
2. Use `grep` to find domain entities already modelled in code (models, dataclasses, Pydantic
   schemas, ORM classes) — do not re-implement what already exists
3. Check whether `typer` is already a dependency. If not, note it must be added
4. Identify where `commands/` should live relative to the existing package structure

---

## Phase 1 — Implementation

### Technology stack

- **Typer** for CLI parsing and dispatch. Typer infers argument types, required flags, and help
  text directly from Python type annotations — no separate `@click.option` decorators needed.
- **Command Pattern** for business logic. One class per resource (or logical group), not one
  class per subcommand. Typer handles dispatch; command classes encapsulate behaviour.
- Follow the **python-style-guide** conventions: modern type hints (`X | None`, `list[str]`),
  Google docstrings, ruff formatting, `uv` for dependency management.

### Project structure

```
<project-name>/
├── pyproject.toml
├── README.md
└── src/
    └── <project_name>/
        ├── __init__.py
        ├── cli.py                      ← Typer app wiring only, no business logic
        └── commands/
            ├── __init__.py
            ├── base.py                 ← Marker ABC
            ├── <resource>_command.py   ← One file per resource or logical group
            └── ...
```

### Step 1.1 — Add dependency

If `typer` is not already present:

```
execute_command: uv add typer
```

### Step 1.2 — Create `commands/base.py`

The base class is a **marker** only. Typer handles dispatch, so no shared `execute(args)` method:

```python
from abc import ABC


class Command(ABC):
    """Marker base class for CLI commands.

    Typer handles argument parsing and command dispatch.
    Each subclass defines its own typed method signatures.
    """
```

### Step 1.3 — Create one command class per resource

One file per resource from the command table in `docs/cli-design.md`.
Nested sub-resource operations live on the **parent** resource command class when the
relationship is strong. Extract to its own class only if the parent file exceeds ~120 lines.

```python
# commands/<resource>_command.py
from .base import Command


class <Resource>Command(Command):
    """Encapsulates all <resource> operations."""

    def list(self) -> None:
        """List all <resources>."""
        ...

    def add(self, name: str) -> None:
        """Create a new <resource>."""
        ...
```

### Step 1.4 — Wire `cli.py`

`cli.py` contains **only wiring** — Typer app declarations, `add_typer` calls, and thin wrapper
functions that delegate immediately to command classes. No business logic here.

```python
import typer

from <project_name>.commands.<resource>_command import <Resource>Command

app = typer.Typer(help="<CLI description>", no_args_is_help=True)

resource_app = typer.Typer(help="Manage <resources>", no_args_is_help=True)
app.add_typer(resource_app, name="<resource>")

_resource = <Resource>Command()


@resource_app.command("list")
def resource_list() -> None:
    """List all <resources>."""
    _resource.list()


@resource_app.command("add")
def resource_add(
    name: str = typer.Option(..., "--name", "-n", help="<Resource> name"),
) -> None:
    """Create a new <resource>."""
    _resource.add(name=name)


def main() -> None:
    app()
```

### Step 1.5 — Add entry point to `pyproject.toml`

```toml
[project.scripts]
<cli-name> = "<project_name>.cli:main"
```

### Step 1.6 — Configuration module (if needed)

If `docs/cli-design.md` defines a configuration convention, create `src/<package>/config.py`:

```python
import os
from pathlib import Path

_PROJECT_PATH = Path(os.environ.get("<CLI_NAME>_PATH", str(Path.home() / ".<cli-name>")))
CONFIG_PATH = _PROJECT_PATH / "cli" / "config.yaml"


def load() -> Config:
    """Read and parse the config file. Returns defaults if absent."""
    ...


def save(cfg: Config) -> None:
    """Write the config, creating parent directories as needed."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ...
```

Command classes receive config via **constructor injection** — they never call `config.load()`
directly.

### Step 1.7 — Domain models (if needed)

If the CLI exchanges typed data (API responses, config structures), represent them as
**dataclasses** (or Pydantic models if validation is needed) in `src/<package>/models/`:

```
src/<package>/models/
├── __init__.py       ← re-exports every public class
├── <entity>.py       ← one file per entity or logical group
```

`__init__.py` re-exports everything — callers write `from <package>.models import Foo`,
never the full internal path.

---

## Phase 2 — Validation

Run in order:

```
execute_command: uv pip install -e .
```

Smoke-test every usage example from `docs/cli-design.md`.

```
execute_command: ruff check . && ruff format .
execute_command: mypy src/
```

Fix all mypy errors before declaring done.

---

## Implementation checklist

- [ ] `docs/cli-design.md` exists and was read
- [ ] Scaffold confirmed complete (`pyproject.toml`, `src/`, `.python-version`, `uv.lock`)
- [ ] `uv add typer` (if not already present)
- [ ] `commands/base.py` written
- [ ] One command class per resource from the command table — no duplication of existing code
- [ ] `cli.py` wired — wiring only, no business logic
- [ ] Entry point added to `pyproject.toml`
- [ ] Config module written (if `docs/cli-design.md` defines configuration)
- [ ] `uv pip install -e .` and every usage example smoke-tested
- [ ] `ruff check . && ruff format .` — clean
- [ ] `mypy src/` — zero errors

---

## Key design rules (always apply)

1. **cli-design is the spec.** Never invent commands not in `docs/cli-design.md`. If something
   is missing, ask the user to update the design first with `/cli-design`.
2. **Typer dispatches, command classes encapsulate.** `cli.py` is wiring only.
3. **One command class per resource** — subcommands are methods, not separate classes.
4. **No shared `execute(args)` method.** Each method has its own typed signature.
5. **Help text on every command and option.** Every `Typer()` app must use `no_args_is_help=True`.
   Every `typer.Option` must carry a `help=` string.
6. **File size discipline.** Keep every `*_command.py` under ~120 lines. When it grows beyond:
   - Extract large data blobs into a private `_<resource>_<concern>.py` module
   - If the class still has too many methods, split into a `commands/<resource>/` sub-package
     with `__init__.py` re-exporting the command class
   - Never split the command class itself across files — one class, one module
7. **Typed signatures are the spec.** If mypy complains, the design has a gap.
