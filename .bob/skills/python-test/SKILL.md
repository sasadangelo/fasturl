---
name: python-test
description: "Use when implementing tests for a Python project — writes unit, integration, and e2e test suites using pytest, guided by docs/test-strategy.md. Applies to any project type: REST API, web app, CLI, batch processing, or library. Run after /test-strategy."
metadata:
  disable-model-invocation: false
  argument-hint: "[unit|integration|e2e|all]"
---

# Python Test Implementer

Implement automated tests for a Python project following the decisions recorded in `docs/test-strategy.md`.
Uses **pytest** as the base framework. Add `pytest-asyncio` only if the project uses async code.

Produces or updates:
- `tests/unit/` — isolated single-function/component tests
- `tests/integration/` — cross-boundary tests (DB, external adapters, framework wiring)
- `tests/e2e/` — full workflow tests through the system's public entry point
- `tests/conftest.py` — shared fixtures adapted to the project type

Do not alter application source code or architecture. If a required guarantee cannot be met without
changing application code, describe the gap and ask before proceeding.

---

## Step 0 — Discover Context

Read the following files before writing any test code:

1. `docs/test-strategy.md` — **required**. If absent, stop and ask the user to run `/test-strategy` first.
2. `docs/requirements.md` — requirements, job stories, or acceptance criteria to derive test scenarios.
3. `docs/architecture.md` — layer map, component responsibilities, async patterns.
4. `docs/tech-stack.md` — framework, language version, key dependencies.
5. `pyproject.toml` or `setup.cfg` — existing pytest config, installed dependencies, tool settings.
6. `src/` (or the project's main source directory) — understand the module structure being tested.
7. Existing `tests/` directory — avoid duplicating tests that already exist.

From the stack and architecture, identify the **project type** — this drives fixture and integration
strategy choices in the steps below:

| Project type           | Entry point under test           | Typical integration boundary         |
|------------------------|----------------------------------|--------------------------------------|
| REST API (FastAPI)     | HTTP routes via ASGI transport   | DB session, HTTP client              |
| Web app (Flask/Django) | HTTP routes via test client      | DB session, HTTP client              |
| CLI (Typer/Click)      | `CliRunner` or subprocess        | File system, external services       |
| Batch / worker         | Task function or `main()`        | DB, message queue, file system       |
| Library / SDK          | Public API functions             | External services, file system       |

Note which test categories (`unit`, `integration`, `e2e`) are in scope based on what the user
requested (argument hint) or on what `docs/test-strategy.md` prescribes.

---

## Step 1 — Confirm Scope

If the user did not specify which category to implement, ask using `ask_followup_question`:
- `unit` — isolated function/component tests only
- `integration` — cross-boundary tests only
- `e2e` — full workflow tests only
- `all` — all three categories

Do not ask if the answer is already clear from the invocation argument or from the conversation.

---

## Step 2 — Design the Test Layout

Map the source layout to the test layout before writing any file.

### Directory structure
```
tests/
├── conftest.py              ← shared fixtures adapted to the project type
├── unit/
│   ├── __init__.py
│   └── test_<module>.py    ← one file per module under test
├── integration/
│   ├── __init__.py
│   └── test_<boundary>.py  ← one file per integration boundary
└── e2e/
    ├── __init__.py
    └── test_<workflow>.py  ← one file per user-facing workflow
```

### Category boundaries (apply strictly)

| Category    | What it tests                                                    | Isolation rule                                                                                |
|-------------|------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| Unit        | A single function or class method in isolation.                  | No real DB, no real network, no real framework routing. Mock/fake only external dependencies. |
| Integration | Multiple real components exercised across a real boundary.       | No mocks for the boundary under test. Use real (in-memory or test) infrastructure.            |
| E2E         | A complete user-visible workflow through the public entry point. | No mocks. Drive the system as an external caller would. Validate observable outcomes.         |

---

## Step 3 — Write Shared Fixtures (`tests/conftest.py`)

Always write `conftest.py` first. Fixtures must be adapted to the project type identified in Step 0.

**General rules for all project types:**
- Keep fixtures function-scoped by default to ensure test isolation.
- Provide session-scoped setup only for expensive, read-only resources.
- If the project uses async code, configure `asyncio_mode = "auto"` in `pyproject.toml` and use `pytest-asyncio`.
- Never hardcode secrets or production URLs in fixtures — use env vars or test-specific config.

**Fixture guidance by project type:**

*REST API (async, e.g. FastAPI + SQLAlchemy async):*
- In-memory DB engine (`create_async_engine`) with `create_all` / `drop_all` per test.
- `AsyncSession` bound to the test engine.
- App instance with the real DB dependency overridden by the test session.
- `httpx.AsyncClient` with `ASGITransport` for driving HTTP.

*REST API (sync, e.g. Flask):*
- Test DB (SQLite in-memory or dedicated test schema).
- Framework test client (`app.test_client()` or equivalent).

*CLI (Typer/Click):*
- `CliRunner` from the framework for invoking commands in-process.
- Temporary directories (`tmp_path`) for file system isolation.

*Batch / worker:*
- In-memory or test DB, pre-seeded with fixture data.
- Patched external service clients (message queue, S3, etc.).

*Library / SDK:*
- No special runtime fixtures. Focus on deterministic inputs/outputs.
- Use `responses` or `respx` to mock HTTP if the library calls external APIs.

---

## Step 4 — Implement Unit Tests

Scope: pure business logic — functions and methods that have no dependency on infrastructure.

Regardless of project type:
1. Identify the public functions/methods with non-trivial logic in the business/service layer.
2. For each function derive test cases from:
   - Acceptance criteria or requirements (happy path).
   - Edge cases and error conditions described in requirements.
   - Business invariants from `docs/domain-design.md` if present.
3. Write one test per case, or group related cases in a class when they share setup.
4. Use `unittest.mock.patch` or `pytest-mock` only to replace **external** dependencies
   (DB calls, HTTP calls, file I/O). Never mock the function under test or its own internal sub-calls.

Naming: `tests/unit/test_<module_name>.py`

---

## Step 5 — Implement Integration Tests

Scope: real components exercised across a real boundary — DB, framework routing, external adapter.

The specific approach depends on the project type identified in Step 0:

*REST API:* Test each endpoint. Assert HTTP status code, response shape, and (where relevant) DB state.
*CLI:* Invoke each command via the test runner. Assert exit code, stdout/stderr output, and side-effects (files created, DB records written).
*Batch / worker:* Call task functions directly with a real test DB. Assert DB state after execution.
*Library:* Exercise the public API against real or stubbed external dependencies.

General rules:
- Derive scenarios from acceptance criteria in requirements (one test per criterion where practical).
- Cover: happy path, validation/input errors, not-found cases, conflict cases.
- Use the fixtures from `conftest.py` — do not instantiate infrastructure directly in test files.

Naming: `tests/integration/test_<boundary_name>.py`

---

## Step 6 — Implement E2E Tests

Scope: complete user-visible workflows driven through the system's public entry point.

Identify the entry point from the project type:
- REST API → HTTP requests via the test client.
- CLI → subprocess or `CliRunner` invocation of the full command chain.
- Batch / worker → trigger the top-level entry point (`main()` or equivalent).
- Library → call the top-level public API as a consumer would.

Each test must:
1. Drive the system only through its public interface — no internal function calls.
2. Assert the final observable state (response, output, file, DB record).
3. Not assert internal implementation details (call counts, mock interactions, private state).

Derive one test file per bounded workflow from the requirements. Cover the full lifecycle where
the requirements define it (create → use → update → delete, or equivalent for the project type).

Naming: `tests/e2e/test_<workflow_name>.py`

---

## Step 7 — Update `pyproject.toml`

Add or update the `[tool.pytest.ini_options]` section:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"   # only if the project uses async code
testpaths = ["tests"]
```

Add test runner shortcuts under `[tool.poe.tasks]` if `poethepoet` is present:

```toml
[tool.poe.tasks]
test-unit        = "pytest tests/unit -v"
test-integration = "pytest tests/integration -v"
test-e2e         = "pytest tests/e2e -v"
test             = "pytest tests/ -v"
test-cov         = "pytest tests/ --cov=src --cov-report=term-missing"
```

---

## Step 8 — Validate

After writing all test files, run the implemented suite:

```bash
pytest tests/<category> -v
```

Fix any import errors, fixture mismatches, or async configuration issues before reporting done.
If a test reveals a genuine bug in the application, report it to the user — do not silently fix
application code.

---

## Reminders

- Follow the style conventions in `.bob/skills/python-style-guide/SKILL.md` if present.
- Keep tests deterministic: no `time.sleep`, no real network calls, no random seeds without fixing them.
- One assertion focus per test — test one behavior, not five at once.
- Do not add test coverage for framework internals, ORM internals, or third-party library behavior.
- Only add `pytest-asyncio` and async fixtures if the project actually uses async code.
