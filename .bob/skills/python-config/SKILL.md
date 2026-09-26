---
name: python-config
description: Use when the user types /add-python-config or /update-python-config with one or more config.yaml and/or .env paths — generates or updates the Pydantic Settings configuration module for a Python project.
metadata:
  argument-hint: "<config.yaml> [.env] [...]"
  disable-model-invocation: true
---

# Python Config Generator

Generates or updates a Pydantic Settings configuration module from one or more input files.

## Commands

- `/add-python-config <file> [file ...]` — generate config module(s) from scratch
- `/update-python-config <file> [file ...]` — regenerate/update after input files changed

Both commands accept any combination of `config.yaml` and `.env` / `.env.example` files.
All files are treated as belonging to the **same project** and merged into a single `Settings` class.

---

## Step 1 — Read all input files

Use `read_file` on every path provided by the user.

For each file classify it:
- **YAML** (`config.yaml`, `config.yml`) → non-secret configuration parameters
- **ENV** (`.env`, `.env.example`) → secret and environment-only parameters

Parse mentally:
- YAML: list every top-level **section** and every **field** within it, with its current value.
- ENV: list every variable name and its placeholder/example value.

---

## Step 2 — Determine project name and output path

Derive the **project name** from the directory containing the first input file:
- e.g. `src/golem-runner/config.yaml` → project = `golem-runner` → Python identifier `golem_runner`

Output path rules:
- Total config fields across all sections **≤ 15** and sections **≤ 3** → single file:
  `src/<project>/core/config.py`
- Otherwise → package:
  - `src/<project>/core/config/__init__.py` — root `Settings` class
  - `src/<project>/core/config/<section>.py` — one file per section

---

## Step 3 — Classify every field

For each field from YAML and ENV, apply these rules in order:

1. **Non-empty, non-placeholder value in YAML?**
   → Use as Pydantic `default`. Mark **optional**.

2. **Empty, `null`, or placeholder value** (e.g. `"your-key-here"`, `"<fill-me>"`, `"TODO"`)?
   → Field is **required** (no default → Pydantic raises at startup if missing).

3. **Field name signals a secret** (contains `key`, `password`, `secret`, `token`, `credential`, `api_key`)?
   → Mark as **secret**: must come from env var only, never from YAML.
   → Load it in `model_post_init` via `os.getenv(...)`.
   → If found in YAML, warn the user to move it to `.env`.

4. **Comes from an ENV file?**
   → Always treat as **secret** (env-only). Map to the corresponding section field if a YAML
   section exists for it, otherwise add it directly to `Settings`.

5. **Genuinely ambiguous** (present in YAML but unclear if it is meaningful or a placeholder)?
   → Use `ask_followup_question` to clarify. Group multiple ambiguous fields into one question.

---

## Step 4 — Generate the Pydantic Settings code

### Key rules

- Use `pydantic-settings` throughout (`BaseSettings`, `SettingsConfigDict`).
- Each YAML top-level section → its own `class <Section>Config(BaseSettings)`.
  Use `BaseSettings` (not `BaseModel`) so each section can independently load its own env vars.
- The root class is always `class Settings(BaseSettings)` with one attribute per section.
- `model_config` uses `SettingsConfigDict` (Pydantic v2 — no `class Config`).
- The root `Settings.model_config` declares both `yaml_file` and `env_file` so Pydantic merges
  both sources automatically:
  ```python
  model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
      yaml_file="config.yaml",
      env_file=".env",
      env_file_encoding="utf-8",
      extra="ignore",
  )
  ```
- Secrets are **not** in `model_config` YAML loading. They are injected in `model_post_init`:
  ```python
  def model_post_init(self, __context: Any) -> None:
      secret = os.getenv("MY_SECRET")
      if secret:
          self.section.secret_field = secret
  ```
- Field types: infer from YAML values (`str`, `int`, `float`, `bool`, `list[str]`). Use `str` when uncertain.
- Required fields: declared with type only, no default → `field_name: type`
- Optional fields: `field_name: type = <default>`
- Use `Field(default=..., description="...")` for every field — always include a description.
- Add `extra="ignore"` on each section config to tolerate unknown keys.
- Add a module-level docstring on every generated file.

### Singleton at module level

At the bottom of the config module (or `__init__.py`), always expose:

```python
settings: Settings = Settings()
```

This is the **single source of truth** for the entire application. All other modules import
`settings` from here — never instantiate `Settings()` anywhere else.

### Fail-fast: no logging, no try/except

`Settings()` is called at import time. Any `ValidationError` raised by Pydantic will propagate as
an unhandled exception and crash the process with a readable traceback — this is the correct
behaviour.

Do **not** wrap `Settings()` or its import in a `try/except`. Do **not** use `logging.*` anywhere
in the config module. Configuration is the lowest-level component in the dependency hierarchy —
logging depends on config, never the reverse.

Simply import `settings` at the top of every module that needs it:

```python
from core.config import settings
```

---

## Step 5 — Write the file(s)

Use `write_file` to create the output path(s) from Step 2.
`write_file` creates missing directories automatically.

---

## Step 6 — Update .env.example

Read the existing `.env.example` (if any) at `src/<project>/.env.example`.

Apply these changes:
- Add a header comment block:
  ```
  # Secrets only — all non-secret configuration lives in config.yaml
  ```
- Remove any variables that are non-secrets and already covered by `config.yaml`.
- Ensure every secret field identified in Step 3 has a commented placeholder entry.
- Leave existing comments intact.

Use `apply_diff` if the file exists, `write_file` if creating from scratch.

---

## Step 7 — Update pyproject.toml

Open `src/<project>/pyproject.toml` (or `requirements.txt` if no pyproject exists).

Add the following dependencies if not already present:

```toml
"pydantic-settings>=2.2.0",
"pyyaml>=6.0",
```

Remove `python-dotenv` if present — `pydantic-settings` handles `.env` loading natively.

---

## Step 8 — Update the entry point

Find `main.py` (or equivalent entry point) in `src/<project>/`.

- Add `from core.config import settings` near the top, before any other config-dependent import.
- Remove `os.getenv(...)` calls whose values are now managed by `settings`.
- Remove any `load_dotenv()` calls — no longer needed.
- Do **not** refactor anything else. Minimal change only.

---

## Step 9 — Report to the user

Summarise:
- Files created or updated (with clickable paths).
- Fields marked **required** — user must supply them at runtime.
- Fields marked **secret** — must be in `.env` only, never in `config.yaml`.
- Any assumptions made about types or defaults.
