# FastURL — Smart Link Shortener & Inspector

## 1. Overview & Vision
**FastURL** is a modern, high-performance REST API built in Python using **FastAPI**. It combines standard URL shortening functionality (CRUD + HTTP redirect) with an asynchronous **Link Health Inspector & Metadata Extractor** executed in the background.

The project serves as a real-world, production-ready reference implementation demonstrating:
- Layered / Clean Architecture with FastAPI.
- Robust schema validation and serialization using **Pydantic v2**.
- Fail-fast configuration management via **Pydantic Settings** and `config.yaml`.
- Async database persistence with **SQLAlchemy ORM** + `aiosqlite` (SQLite).
- Structured logging with **Loguru**.
- Resilient, standardized global error handling.
- Practical concurrency using **BackgroundTasks** and non-blocking HTTP clients (`httpx`).

> **Note on Scope**: Authentication and authorization are deliberately **out of scope** for this phase and will be addressed in dedicated future extensions.

---

## 2. Core Functional Requirements

### A. Link Management (CRUD & Redirection)
1. **Create Short Link (`POST /api/v1/links`)**:
   - Accepts a target URL (`target_url`), an optional custom code/alias (`custom_code`), and an optional title/tags.
   - Validates URL syntax and ensures no self-redirect / redirect loops.
   - If no custom alias is provided, generates a cryptographically secure random alphanumeric code (default length: 7 characters).
   - Persists the link in state `pending_analysis` and immediately responds with `201 Created` containing the full short URL (`http://<base_url>/<code_id>`).
   - Dispatches an asynchronous **Background Task** for link inspection.

2. **Retrieve Link Details & Metrics (`GET /api/v1/links/{code}`)**:
   - Returns full metadata of the link: original URL, short URL, current inspection status (`pending_analysis`, `active`, `unreachable`), HTTP status of target, page title, response latency, creation timestamp, and total click count.

3. **List Links (`GET /api/v1/links`)**:
   - Paginated list of created links with basic filtering (by status, tags).

4. **Delete / Disable Link (`DELETE /api/v1/links/{code}`)**:
   - Soft-deletes or removes the short link.

5. **Perform Redirection (`GET /{code}`)**:
   - Public entry point for URL redirection.
   - Resolves the code to the target URL.
   - Increments click counter and updates last accessed timestamp.
   - Returns HTTP `307 Temporary Redirect` (or `302 Found`).
   - Returns standard `404 Not Found` payload if code does not exist or is disabled.

---

### B. Background Link Inspector & Metadata Extractor
Triggered immediately upon link creation without blocking the client response:
1. **Target Reachability & Latency**:
   - Performs a non-blocking HTTP request (using `httpx.AsyncClient`) to the `target_url` respecting configured timeouts and redirect limits.
   - Measures response time in milliseconds.
2. **Metadata Extraction**:
   - Extracts page `<title>` and OpenGraph tags (`og:title`, `og:description`, `og:image`) if available.
3. **Status Update**:
   - Updates the link record in the database with status `active` (if 2xx/3xx response) or `unreachable` (if connection timeout/failure or 4xx/5xx).

---

## 3. Technical Constraints & Design Guidelines

### A. Architecture & Layer Separation
- **Routers (`app/routers/`)**: Handle HTTP transport, status codes, query/path parameters, and trigger background tasks.
- **Services (`app/services/`)**: Encapsulate business rules, code generation, URL safety checks, and orchestrate repositories.
- **Repositories (`app/repositories/`)**: Async database operations via SQLAlchemy session.
- **Schemas (`app/schemas/`)**: Pydantic v2 DTOs (Request/Response models) with strict type validation.
- **Core (`app/core/`)**: Configuration (`pydantic-settings`), logging (`loguru`), domain exceptions, and global handlers.

### B. Error Handling & Standard Response Contract
All error responses across the API must conform to a standardized JSON schema:

```json
{
  "success": false,
  "error": "Error Category or Message",
  "details": [
    "body -> target_url: Invalid URL scheme (must be http or https)"
  ]
}
```

- **`RequestValidationError`**: Captured globally; transforms Pydantic validation failures into human-readable `loc -> msg` arrays with HTTP `400`.
- **Domain Exceptions**: Custom exceptions (e.g., `LinkNotFoundException`, `AliasAlreadyTakenException`) mapped to clean HTTP status codes (`404`, `409`).
- **Catch-All Exception Handler**: Catches unhandled `Exception`, logs the full stack trace to disk/logger, and returns a safe `500 Internal Server Error` without exposing internal paths or credentials.

### C. Configuration (`config.yaml` & `Settings`)
Loaded via Pydantic Settings into typed models with environment variable override support:

```yaml
app:
  host: "127.0.0.1"
  port: 8000
  base_url: "http://localhost:8000"
  debug: false

database:
  url: "sqlite+aiosqlite:///instance/fasturl.db"
  echo: false

log:
  level: "INFO"
  console: true
  file: "logs/fasturl.log"
  rotation: "10 MB"
  retention: "7 days"
  compression: "zip"

inspector:
  timeout_seconds: 5.0
  max_redirects: 3
```

---

## 4. Key Entities for Domain Design
- **Link**: The aggregate root.
  - Attributes: `id`, `code` (unique indexed), `target_url`, `created_at`, `updated_at`, `is_active`, `clicks_count`, `last_clicked_at`.
- **LinkInspection**: Value object or child entity representing the inspection audit.
  - Attributes: `status` (`pending_analysis`, `active`, `unreachable`), `http_status_code`, `latency_ms`, `title`, `description`, `last_checked_at`.
