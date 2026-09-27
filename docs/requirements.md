# Requirements — FastURL
_Last updated: 2025-05-22_

## Overview
FastURL is a high-performance REST API built with FastAPI that provides URL shortening capabilities (creation, resolution, metrics tracking) coupled with non-blocking, asynchronous background link health inspection and metadata extraction. It is designed as a production-ready service demonstrating clean layered architecture, async persistence, fail-fast configuration, and standardized error contracts.

## Actors
| Actor                  | Description                                                                                                                     | Type           |
|------------------------|---------------------------------------------------------------------------------------------------------------------------------|----------------|
| `API Client`           | An external system, developer, or consumer interacting with the FastURL REST API to manage shortened links and inspect metadata. | System / Human |
| `Public Visitor`       | An internet user or client navigating to a shortened URL (`/{code}`) expecting immediate redirection to the original target destination. | Human / System |
| `Background Inspector` | An internal asynchronous worker process that inspects target URL health, latency, and page metadata after creation.             | System         |

## Job Stories

### Actor: API Client

#### JS-001 — Shorten Target URL with Automatic Code
**When** I provide a valid target URL without specifying a custom alias, **I want to** generate a unique shortened URL with a random alphanumeric code, **so that** I can share a compact link with visitors immediately.

**Acceptance criteria:**
- **Given** a valid HTTP/HTTPS target URL in the request payload (with optional `expires_at` timestamp), **When** I send `POST /api/v1/links`, **Then** the system returns HTTP `201 Created` with the generated 7-character Base62 code, full short URL, expiration time, initial state `pending_analysis`, and triggers background inspection.
- **Given** an invalid URL format or unsupported scheme (non-HTTP/HTTPS), **When** I send `POST /api/v1/links`, **Then** the system returns HTTP `400 Bad Request` with standardized validation details.
- **Given** an expiration date in the past (`expires_at <= now`), **When** I send `POST /api/v1/links`, **Then** the system returns HTTP `400 Bad Request`.
- **Given** a target URL that points to the FastURL service itself (self-redirect), **When** I send `POST /api/v1/links`, **Then** the system rejects the request with HTTP `400 Bad Request` to prevent redirect loops.

**Edge cases / notes:**
- Cryptographically secure Base62 alphanumeric generator (`[a-zA-Z0-9]`) used for default code length (7 characters, ~3.5 trillion keyspace).
- Auto-handles collision retry if random code already exists.

---

#### JS-002 — Shorten Target URL with Custom Alias
**When** I provide a target URL along with a custom alias code, **I want to** assign that specific code to my link, **so that** I have a memorable, branded short URL.

**Acceptance criteria:**
- **Given** a valid target URL and an available custom alias (alphanumeric/hyphens), **When** I send `POST /api/v1/links` with `custom_code`, **Then** the system returns HTTP `201 Created` bound to that code.
- **Given** a custom alias that is already in use by another link, **When** I send `POST /api/v1/links`, **Then** the system returns HTTP `409 Conflict` with an error message indicating the alias is already taken.
- **Given** a custom alias with invalid characters (e.g. spaces, special symbols), **When** I send `POST /api/v1/links`, **Then** the system returns HTTP `400 Bad Request` with validation error details.

---

#### JS-003 — Retrieve Link Details and Inspection Metrics
**When** I query the API with a specific link code, **I want to** view its full metadata, health inspection status, target HTTP response code, latency, and click metrics, **so that** I can verify link health and track usage.

**Acceptance criteria:**
- **Given** an existing active or pending link code, **When** I send `GET /api/v1/links/{code}`, **Then** the system returns HTTP `200 OK` containing target URL, short URL, inspection status (`pending_analysis`, `active`, `unreachable`), page title, OpenGraph metadata, latency in milliseconds, total click count, and timestamps.
- **Given** a non-existent link code, **When** I send `GET /api/v1/links/{code}`, **Then** the system returns HTTP `404 Not Found` with standardized error payload.

---

#### JS-004 — List and Filter Shortened Links
**When** I query the link collection, **I want to** retrieve a paginated list of created links with optional filtering by status and tags, **so that** I can manage my catalogue of short links.

**Acceptance criteria:**
- **Given** multiple links in the database, **When** I send `GET /api/v1/links` with pagination parameters (`page`, `limit`), **Then** the system returns HTTP `200 OK` with the paginated list, total count, and current page metadata.
- **Given** filter query parameters such as `status=active`, **When** I send `GET /api/v1/links?status=active`, **Then** the system returns only links matching that inspection status.

---

#### JS-005 — Delete / Disable Link
**When** a short link is no longer needed or is found to be malicious/stale, **I want to** delete or disable the link, **so that** subsequent requests no longer redirect to the target URL.

**Acceptance criteria:**
- **Given** an existing link code, **When** I send `DELETE /api/v1/links/{code}`, **Then** the system deletes or disables the link and returns HTTP `204 No Content` or `200 OK`.
- **Given** a non-existent link code, **When** I send `DELETE /api/v1/links/{code}`, **Then** the system returns HTTP `404 Not Found`.

---

### Actor: Public Visitor

#### JS-006 — Redirect to Target Destination
**When** I navigate to a short URL (`/{code}`) in my browser or HTTP client, **I want to** be redirected to the target destination URL immediately, **so that** I reach the intended destination without delay.

**Acceptance criteria:**
- **Given** an existing active, non-expired short link code, **When** I request `GET /{code}`, **Then** the system responds with HTTP `307 Temporary Redirect` (or `302 Found`) with the `Location` header pointing to the target URL, ensuring browser cache bypass for accurate click analytics.
- **Given** a successful redirect request, **When** the redirection is served, **Then** the system increments the link's click count by 1 and updates the `last_clicked_at` timestamp.
- **Given** a link that has passed its `expires_at` date, **When** I request `GET /{code}`, **Then** the system responds with HTTP `410 Gone`.
- **Given** a non-existent or deleted/disabled code, **When** I request `GET /{code}`, **Then** the system returns HTTP `404 Not Found`.

---

### Actor: Background Inspector

#### JS-007 — Asynchronously Inspect Target URL Health and Extract Metadata
**When** a new short link is registered, **I want to** perform a non-blocking background check on the target URL, **so that** link reachability, latency, page title, and OpenGraph tags are updated without blocking the initial creation response.

**Acceptance criteria:**
- **Given** a newly created link with state `pending_analysis`, **When** the background task executes, **Then** it performs an HTTP request to `target_url` with configured timeout and max redirect limits.
- **Given** a reachable target URL returning 2xx or 3xx status, **When** analysis completes, **Then** the system updates link status to `active`, records `http_status_code`, `latency_ms`, `<title>`, and OpenGraph tags (`og:title`, `og:description`, `og:image`).
- **Given** an unreachable target URL (DNS failure, connection timeout, 4xx/5xx status), **When** analysis completes, **Then** the system updates status to `unreachable` with the appropriate error details or HTTP status code.

---

#### JS-008 — Manually Trigger Link Re-Inspection
**When** I want to re-check the health of a target URL (e.g., a previously unreachable link may have recovered), **I want to** trigger a new background inspection on demand, **so that** I can refresh the inspection status without waiting for automatic re-inspection.

**Acceptance criteria:**
- **Given** an existing link code (active or unreachable), **When** I send `POST /api/v1/links/{code}/inspect`, **Then** the system returns HTTP `202 Accepted` with the current inspection snapshot (status, timestamps) and dispatches a new background inspection task.
- **Given** a non-existent link code, **When** I send `POST /api/v1/links/{code}/inspect`, **Then** the system returns HTTP `404 Not Found`.
- **Given** a link whose inspection is already in `pending_analysis` state, **When** I send `POST /api/v1/links/{code}/inspect`, **Then** the system still accepts the request and re-queues the task (idempotent trigger).

**Edge cases / notes:**
- The endpoint returns immediately; inspection result is visible via `GET /api/v1/links/{code}` once the background task completes.
- Inspection respects the same configurable timeout and max-redirect limits as the automatic post-creation inspection.

---

## Business Constraints
1. **Self-Redirection Prevention**: A target URL cannot point to the FastURL base URL or create a recursive redirect loop.
2. **Code Uniqueness & Keyspace**: Link codes/aliases must be strictly unique. Auto-generated keys use a 7-character Base62 keyspace (`[a-zA-Z0-9]`) to avoid predictability.
3. **URL Scheme Restrictions**: Only `http` and `https` protocols are allowed as valid target URLs.
4. **Non-blocking Creation**: The link creation endpoint `POST /api/v1/links` MUST respond immediately to the client without waiting for the link inspection HTTP request to finish.
5. **Redirect Semantics (307/302 vs 301)**: Redirections MUST use temporary redirect status codes (307/302) to prevent aggressive browser caching and preserve click tracking.
6. **Standardized Error Envelope**: All API errors must follow the unified `{ "success": false, "error": string, "details": list }` schema.

7. **Manual Re-Inspection**: Clients can trigger re-inspection of any existing link via `POST /api/v1/links/{code}/inspect`. The endpoint responds immediately with `202 Accepted`; inspection runs asynchronously.

## Non-Functional Requirements
| Category                    | Requirement                                                                                                                                           |
|-----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Performance**             | API endpoint response latency < 50ms at p95 for redirection and CRUD operations (excluding target URL background inspection).                         |
| **Concurrency & Async**     | Non-blocking asynchronous I/O using FastAPI, `httpx.AsyncClient`, and `SQLAlchemy` with `aiosqlite`.                                                  |
| **Inspector Limits**        | Configurable HTTP request timeout (default: 5.0s) and max redirect limit (default: 3) for target inspection to avoid hanging connections.             |
| **Logging & Observability** | Structured logging with Loguru; file rotation (10 MB), retention (7 days), compression (zip), and console formatting. No sensitive payload logging.    |
| **Configuration**           | Fail-fast typed configuration via Pydantic Settings with YAML support (`config.yaml`) and environment variable overrides.                              |
| **Persistence**             | SQLite with async driver (`aiosqlite`) via SQLAlchemy ORM.                                                                                            |

## Out of Scope
- User authentication and authorization (RBAC / API keys / OAuth2) — planned for a future milestone.
- Custom domain branding / multi-tenant routing.
- Advanced analytics dashboard UI (frontend client).
- QR code generation for shortened URLs.
- Automated periodic database vacuum/purging of expired links (lazy expiration on access is used).

## Open Questions
- Should unreachable links still redirect visitors (with a warning/pass-through) or immediately return 404/warning page? *(Default: still redirect unless disabled).*
- Will rate-limiting per IP be introduced in the next phase alongside authentication?

## Change Log
| Version | Date       | Change                                                                                                                                                   |
|---------|------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0.1     | 2025-05-15 | Initial requirements extracted from idea.md covering Link CRUD, Redirection, and Background Inspection                                                    |
| 0.2     | 2025-05-15 | Integrated key system design concepts: Base62 7-char keyspace, temporary redirect semantics (307/302 for metrics), and lazy link expiration (410 Gone)   |
| 0.3     | 2025-05-22 | Added JS-008 (Manual Re-Inspection trigger) and Business Constraint #7                                                                                    |
