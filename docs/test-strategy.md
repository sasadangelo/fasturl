# Test Strategy — FastURL
_Last updated: 2025-05-22_

## 1. Scope and Goals

FastURL is a single-process FastAPI monolith that provides URL shortening, redirection, and asynchronous background inspection. This strategy covers all eight job stories (JS-001–JS-008) and all six business constraints defined in `docs/requirements.md`.

**Primary goal:** gain confidence that the observable HTTP contracts and domain invariants are correct before any code reaches `main`.  
**Secondary goal:** keep the feedback loop short enough to run on every pull request without a dedicated CI environment.

Authentication, multi-tenancy, a frontend, and load testing are explicitly out of scope for the current milestone.

---

## 2. Risk / Requirement Mapping

| Risk                                                                 | Affected requirement       | Evidence type      |
|----------------------------------------------------------------------|----------------------------|--------------------|
| URL validation bugs (bad scheme, self-redirect, past expiry)         | JS-001, JS-002, BC-1, BC-3 | Unit + Integration |
| Base62 collision retry failure                                        | JS-001, BC-2               | Unit               |
| Expired link not returning `410 Gone`                                | JS-006, BC-5               | Integration        |
| Background inspection silently failing (DB never updated)            | JS-007, JS-008             | Unit + Integration |
| Error envelope contract broken                                        | BC-6                       | Integration        |
| Click count not incrementing on redirect                             | JS-006                     | Integration        |
| Inactive / soft-deleted link still redirecting                       | JS-005, JS-006             | Integration        |
| Custom alias conflict not returning `409`                            | JS-002                     | Integration        |
| Re-inspection when already `pending_analysis` accepted (idempotent)  | JS-008                     | Integration        |
| HTML metadata extraction returning wrong field                       | JS-007                     | Unit               |

---

## 3. Test Categories

### 3.1 Unit Tests

**Primary assurance:** one behaviour in isolation — a focused function, method, or pure business rule.

**Boundaries in this project:**
- `LinkService` — code generation (`_generate_code`), self-redirect guard (`_validate_target_url`), expiry enforcement (`resolve_for_redirect`), sort-field validation (`list_links`), and collision-retry logic (`create_link`).
- `InspectorService` helpers — `_extract_title`, `_extract_description`, `_extract_image_url`.

**Substitutes used:** `LinkRepository` replaced by a synchronous/async mock or stub; `httpx.AsyncClient` replaced by `httpx.MockTransport` or an inline stub. No database engine is instantiated.

**Folder:** `tests/unit/`

---

### 3.2 Integration Tests

**Primary assurance:** components work correctly across real layer boundaries — router → service → repository → ORM → in-memory SQLite.

**Boundaries in this project:**  
All five management endpoints and the public redirect endpoint exercised via FastAPI's in-process `AsyncClient` (`httpx.AsyncClient(app=app, base_url="http://test")`). The real SQLite engine is used (`:memory:` database); Pydantic validation, exception handlers, and the full layered stack execute as in production.

**Background inspection:** called directly as a coroutine (not via `BackgroundTasks` dispatch) so that the effect on the DB state is synchronously observable in the same test. The `httpx.AsyncClient` used by the inspector is replaced by a `respx`-mocked or `httpx.MockTransport`-based stub — no real outbound HTTP.

**Scope per endpoint:**

| Endpoint                            | Scenarios verified                                                                                                                                                      |
|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `POST /api/v1/links`                | Valid auto-code → 201; valid custom alias → 201; invalid URL scheme → 400; self-redirect → 400; past expiry → 400; duplicate alias → 409; invalid alias chars → 400    |
| `GET /api/v1/links`                 | Returns list; filters by `status`; filters by `is_active`; invalid sort → 400                                                                                          |
| `GET /api/v1/links/{code}`          | Found → 200 with full payload; not found → 404                                                                                                                          |
| `DELETE /api/v1/links/{code}`       | Existing → 204; not found → 404                                                                                                                                         |
| `POST /api/v1/links/{code}/inspect` | Existing → 202 + status reset to `pending_analysis`; not found → 404; already pending → 202 (idempotent)                                                               |
| `GET /{code}`                       | Active → 307 + `Location` header + click count incremented; inactive → 404; expired → 410; not found → 404                                                             |

**Folder:** `tests/integration/`

---

### 3.3 End-to-End Tests

Not mandated at the current milestone. The integration layer already exercises the full internal stack through the public HTTP surface. End-to-end tests against a deployed container are deferred to the milestone that introduces authentication and containerised deployment.

---

## 4. Isolation, Data, and Determinism Policy

| Concern                   | Policy                                                                                                                                                                              |
|---------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Database isolation**    | Each integration test (or test module) receives a fresh in-memory SQLite session via an async fixture that runs `create_all` before the test and `drop_all` after. No test depends on state left by another. |
| **Execution order**       | All tests must be independently runnable. `pytest -p no:randomly` is not required; tests must not break when shuffled.                                                              |
| **Time / expiry**         | `datetime.utcnow()` calls that affect business rules (expiry checks) are controlled by injecting explicit past or future timestamps in test fixtures. `freezegun` may be used for service-layer unit tests. |
| **Randomness**            | `random.choices` in `_generate_code` is not seeded; the actual random output is acceptable. Collision-retry logic is tested by pre-populating codes, not by controlling the PRNG.  |
| **External HTTP**         | All outbound `httpx.AsyncClient` calls made by `InspectorService` are intercepted via `respx` or `httpx.MockTransport`. No real network calls occur in any test.                   |
| **Secrets / environment** | No `.env` file is loaded in CI. Tests use a dedicated `config.yaml` fixture or environment variable overrides pointing to the in-memory SQLite URL.                                 |
| **Retries**               | No test retry is permitted. A flaky test must be fixed, not silently re-run.                                                                                                        |
| **Parallel execution**    | Integration tests may be run in parallel only if each test has its own isolated session. Until fixture isolation is verified, `pytest -n auto` is opted out for integration tests.  |

---

## 5. Local and CI Execution Matrix

| Command                                                   | Scope                                   | When                    |
|-----------------------------------------------------------|-----------------------------------------|-------------------------|
| `uv run pytest tests/unit`                                | Unit tests only                         | Development, pre-commit |
| `uv run pytest tests/integration`                         | Integration tests only                  | Development, pre-commit |
| `uv run pytest`                                           | All tests                               | Before push, CI         |
| `uv run pytest --tb=short -q`                             | All tests (compact output)              | CI pull-request check   |
| `uv run coverage run -m pytest && uv run coverage report` | Coverage report (no enforced threshold) | CI main-branch push     |

**Required environment for CI:**
- Python 3.12 (from `.python-version`)
- `uv` package manager
- No additional services (SQLite is in-memory; no Docker required)
- No secrets required for the current milestone

**CI gates (to be configured when a workflow file is added):**

| Gate         | Trigger            | Checks                                                                 | Target time |
|--------------|--------------------|------------------------------------------------------------------------|-------------|
| `pr-check`   | Every pull request | `ruff` lint, `mypy` typecheck, `bandit` security scan, full test suite | < 3 min     |
| `full-check` | Push to `main`     | All of the above + coverage report                                     | < 5 min     |

Which failures block delivery: any failure in `pr-check` blocks merge. Flaky tests must be resolved before re-enabling the gate; suppression via `xfail` or retry markers is not permitted without a tracked issue.

---

## 6. Deferred Checks and Known Gaps

| Check                                       | Rationale                                                                                                                                                                                |
|---------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| End-to-end (deployed server / Docker)       | No auth or container requirement at current milestone                                                                                                                                    |
| Performance / load testing                  | Deferred to auth + rate-limiting milestone; no SLO enforcement tool yet                                                                                                                  |
| Security penetration testing                | Covered statically by `bandit`; full pentest deferred to auth milestone                                                                                                                  |
| Click-count atomicity under concurrent load | Not applicable at SQLite / single-process demo scale                                                                                                                                     |
| `BackgroundTasks` dispatch linkage          | Verified by reading the router source; not separately tested. If the wiring ever becomes complex, an integration test that uses `TestClient` with background tasks enabled can be added. |
| Contract (schema) tests                     | Not required — no external consumers; API schema is under full project control                                                                                                           |

---

## 7. Change Log

| Version | Date       | Change                                                                                                  |
|---------|------------|---------------------------------------------------------------------------------------------------------|
| 0.1     | 2025-05-22 | Initial test strategy — unit + integration categories, in-memory SQLite, no e2e, no coverage threshold |
