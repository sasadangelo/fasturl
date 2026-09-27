# REST API Specification — FastURL
_Last updated: 2025-05-22_

## 1. Overview & Architectural Context

### API Version & Base URL
| Environment | Base URL                  |
|-------------|---------------------------|
| Local dev   | `http://127.0.0.1:8000`   |
| Production  | `https://<your-domain>`   |

All management endpoints are versioned under `/api/v1/`. The public redirect endpoint is mounted at the root `/` (no version prefix — it is a consumer-facing URL that must remain stable and short).

### Identifier Strategy
- **Public identifier:** `code` — Base62 alphanumeric string, 7 chars (auto-generated) or 7–16 chars (custom alias). Non-sequential, non-enumerable by design.
- **Internal identifier:** `id` (INTEGER PK) — never exposed in any API response or path.

### Authentication & Authorization
Authentication is **out of scope for the current milestone** (see `requirements.md` — Out of Scope). All endpoints are currently unauthenticated. Rate-limiting per IP is planned for a future milestone alongside auth.

### Async Inspection Convention
Inspection (both automatic post-creation and manual re-trigger) is **fire-and-forget** via FastAPI `BackgroundTasks`. The client receives a `202 Accepted` with the current inspection snapshot. Updated results are polled via `GET /api/v1/links/{code}`.

### Error Envelope
All error responses follow the unified contract:
```json
{
  "success": false,
  "error": "SHORT_ERROR_CODE",
  "details": [
    "field_name -> Explanation of the validation or business rule failure"
  ]
}
```

---

## 2. Resource Hierarchy & Endpoint Map

| Domain Entity    | REST Resource                  | Methods         | Notes                              |
|------------------|--------------------------------|-----------------|------------------------------------|
| `Link`           | `/api/v1/links`                | `GET`, `POST`   | Collection: list & create          |
| `Link`           | `/api/v1/links/{code}`         | `GET`, `DELETE` | Instance: detail & soft-delete     |
| `LinkInspection` | `/api/v1/links/{code}/inspect` | `POST`          | Action: manual re-inspection       |
| *(public)*       | `/{code}`                      | `GET`           | Redirect router — no `/api/v1/`    |

---

## 3. Detailed Endpoint Specifications

---

### `POST /api/v1/links`

- **Tag:** Links
- **Summary:** Create a new shortened link
- **Description:** Creates a new `Link` aggregate. If `custom_code` is omitted, a random 7-character Base62 code is generated. On success, a background inspection task is automatically dispatched to check target URL health and extract OpenGraph metadata. Responds immediately with `201 Created` without waiting for inspection to complete.

**Request Body** (`application/json`)

| Field        | Type               | Required | Constraints                                          |
|--------------|--------------------|----------|------------------------------------------------------|
| `target_url` | `string` (URL)     | ✅       | Must be HTTP/HTTPS; cannot point to FastURL base URL |
| `custom_code`| `string`           | ❌       | Base62 `[a-zA-Z0-9]`, 7–16 chars                     |
| `expires_at` | `string` (ISO 8601)| ❌       | Must be a future datetime if provided                |

```json
{
  "target_url": "https://example.com/very/long/article/path",
  "custom_code": "mybrand",
  "expires_at": "2026-01-01T00:00:00Z"
}
```

**Responses**

`201 Created`
```json
{
  "code": "mybrand",
  "short_url": "http://127.0.0.1:8000/mybrand",
  "target_url": "https://example.com/very/long/article/path",
  "is_active": true,
  "expires_at": "2026-01-01T00:00:00Z",
  "inspection": {
    "status": "pending_analysis",
    "http_status_code": null,
    "latency_ms": null,
    "title": null,
    "description": null,
    "image_url": null,
    "last_checked_at": null
  },
  "metrics": {
    "clicks_count": 0,
    "last_clicked_at": null
  },
  "created_at": "2025-05-22T10:00:00Z",
  "updated_at": "2025-05-22T10:00:00Z"
}
```

`400 Bad Request` — Invalid URL, unsupported scheme, past expiration, self-redirect, invalid code format
```json
{
  "success": false,
  "error": "VALIDATION_ERROR",
  "details": [
    "target_url -> URL scheme must be http or https",
    "expires_at -> Expiration date must be in the future"
  ]
}
```

`409 Conflict` — Custom alias already taken
```json
{
  "success": false,
  "error": "ALIAS_ALREADY_TAKEN",
  "details": [
    "custom_code -> The alias 'mybrand' is already in use"
  ]
}
```

---

### `GET /api/v1/links`

- **Tag:** Links
- **Summary:** List all shortened links with optional filtering
- **Description:** Returns a flat array of all links in the system. Supports filtering by inspection status and operational state. No pagination — the dataset is intentionally small (demo scope, no multi-user auth). Primarily useful for debugging and manual inspection during development.

**Query Parameters**

| Name        | Type      | Default      | Validation                                                                                |
|-------------|-----------|--------------|-------------------------------------------------------------------------------------------|
| `status`    | `string`  | —            | `pending_analysis` \| `active` \| `unreachable`                                           |
| `is_active` | `boolean` | `true`       | `true` \| `false`                                                                         |
| `sort`      | `string`  | `-created_at`| Comma-separated fields; prefix `-` for descending. Allowed: `created_at`, `clicks_count` |

**Responses**

`200 OK`
```json
[
  {
    "code": "aB3x9zK",
    "short_url": "http://127.0.0.1:8000/aB3x9zK",
    "target_url": "https://example.com/article",
    "is_active": true,
    "expires_at": null,
    "inspection": {
      "status": "active",
      "http_status_code": 200,
      "latency_ms": 142.5,
      "title": "Example Article",
      "description": "An interesting article about examples",
      "image_url": "https://example.com/og-image.png",
      "last_checked_at": "2025-05-22T10:01:00Z"
    },
    "metrics": {
      "clicks_count": 17,
      "last_clicked_at": "2025-05-22T11:30:00Z"
    },
    "created_at": "2025-05-22T10:00:00Z",
    "updated_at": "2025-05-22T10:01:00Z"
  }
]
```

`400 Bad Request` — Invalid query parameter value
```json
{
  "success": false,
  "error": "VALIDATION_ERROR",
  "details": [
    "status -> Must be one of: pending_analysis, active, unreachable"
  ]
}
```

---

### `GET /api/v1/links/{code}`

- **Tag:** Links
- **Summary:** Retrieve full details of a single link
- **Description:** Returns the complete `Link` aggregate including inspection snapshot and click metrics. Returns `404` if the code does not exist (regardless of `is_active` state — deleted links are still retrievable for audit purposes).

**Path Parameters**

| Name   | Type     | Description                            |
|--------|----------|----------------------------------------|
| `code` | `string` | Base62 short code or custom alias      |

**Responses**

`200 OK` — same schema as a single item in `GET /api/v1/links`

`404 Not Found`
```json
{
  "success": false,
  "error": "LINK_NOT_FOUND",
  "details": [
    "code -> No link found with code 'aB3x9zK'"
  ]
}
```

---

### `DELETE /api/v1/links/{code}`

- **Tag:** Links
- **Summary:** Soft-delete (disable) a link
- **Description:** Sets `is_active = false` on the link. The record is retained in the database for audit purposes. After deletion, `GET /{code}` will return `404 Not Found` for visitors attempting to use the short URL.

**Path Parameters**

| Name   | Type     | Description                       |
|--------|----------|-----------------------------------|
| `code` | `string` | Base62 short code or custom alias |

**Responses**

`204 No Content` — Link successfully disabled; no response body.

`404 Not Found`
```json
{
  "success": false,
  "error": "LINK_NOT_FOUND",
  "details": [
    "code -> No link found with code 'aB3x9zK'"
  ]
}
```

---

### `POST /api/v1/links/{code}/inspect`

- **Tag:** Links / Inspection
- **Summary:** Manually trigger a background re-inspection of a link's target URL
- **Description:** Resets `inspection_status` to `pending_analysis` and dispatches a new background inspection task. Responds immediately with `202 Accepted` and the current (pre-inspection) link snapshot. The result is available via `GET /api/v1/links/{code}` once the background task completes. Accepts re-trigger even if the link is already in `pending_analysis` state (idempotent trigger).

**Path Parameters**

| Name   | Type     | Description                       |
|--------|----------|-----------------------------------|
| `code` | `string` | Base62 short code or custom alias |

**Request Body:** None

**Responses**

`202 Accepted`
```json
{
  "code": "aB3x9zK",
  "short_url": "http://127.0.0.1:8000/aB3x9zK",
  "target_url": "https://example.com/article",
  "is_active": true,
  "expires_at": null,
  "inspection": {
    "status": "pending_analysis",
    "http_status_code": null,
    "latency_ms": null,
    "title": null,
    "description": null,
    "image_url": null,
    "last_checked_at": null
  },
  "metrics": {
    "clicks_count": 17,
    "last_clicked_at": "2025-05-22T11:30:00Z"
  },
  "created_at": "2025-05-22T10:00:00Z",
  "updated_at": "2025-05-22T12:00:00Z"
}
```

`404 Not Found`
```json
{
  "success": false,
  "error": "LINK_NOT_FOUND",
  "details": [
    "code -> No link found with code 'aB3x9zK'"
  ]
}
```

---

### `GET /{code}`

- **Tag:** Redirect
- **Summary:** Resolve and redirect a short URL to its target destination
- **Description:** Public endpoint mounted at the root path (no `/api/v1/` prefix). Resolves `code` to its `target_url` and issues an HTTP `307 Temporary Redirect`. Uses `307` (not `301`) to prevent browser caching and preserve accurate click tracking. On successful redirect, atomically increments `clicks_count` and updates `last_clicked_at` via a background update. Returns `410 Gone` for expired links and `404 Not Found` for inactive or non-existent codes.

**Path Parameters**

| Name   | Type     | Description                       |
|--------|----------|-----------------------------------|
| `code` | `string` | Base62 short code or custom alias |

**Responses**

`307 Temporary Redirect` — `Location` header set to `target_url`; no response body.

`404 Not Found` — Code does not exist or link is disabled (`is_active = false`)
```json
{
  "success": false,
  "error": "LINK_NOT_FOUND",
  "details": [
    "code -> No active link found with code 'aB3x9zK'"
  ]
}
```

`410 Gone` — Link has passed its `expires_at` date
```json
{
  "success": false,
  "error": "LINK_EXPIRED",
  "details": [
    "code -> Link 'aB3x9zK' expired on 2025-01-01T00:00:00Z"
  ]
}
```

---

## 4. Asynchronous Job & Polling Contracts

There is no separate job-polling endpoint. Inspection is handled via FastAPI in-process `BackgroundTasks`. The async contract is:

| Step | Action | Result |
|------|--------|--------|
| 1 | `POST /api/v1/links` or `POST /api/v1/links/{code}/inspect` | `201`/`202` returned immediately; `inspection.status = "pending_analysis"` |
| 2 | Background task executes `httpx.AsyncClient.get(target_url)` | Status updated to `"active"` or `"unreachable"` in DB |
| 3 | Client polls `GET /api/v1/links/{code}` | Returns updated `inspection` snapshot |

Inspection timeout: configurable via `config.yaml → inspector.timeout_seconds` (default: 5.0s).  
Max redirects: configurable via `config.yaml → inspector.max_redirects` (default: 3).

---

## 5. Standard Error Envelopes & Codes

### Global Exception Mapping

| Exception / Scenario              | HTTP Status | `error` code            |
|-----------------------------------|-------------|-------------------------|
| Pydantic request validation error | `400`       | `VALIDATION_ERROR`      |
| Invalid URL scheme / format       | `400`       | `VALIDATION_ERROR`      |
| Self-redirect prevention          | `400`       | `VALIDATION_ERROR`      |
| Past expiration date              | `400`       | `VALIDATION_ERROR`      |
| Custom alias already taken        | `409`       | `ALIAS_ALREADY_TAKEN`   |
| Link not found                    | `404`       | `LINK_NOT_FOUND`        |
| Link expired (redirect)           | `410`       | `LINK_EXPIRED`          |
| Rate limit exceeded               | `429`       | `RATE_LIMIT_EXCEEDED`   |
| Unhandled server error            | `500`       | `INTERNAL_SERVER_ERROR` |
| DB / downstream unavailable       | `503`       | `SERVICE_UNAVAILABLE`   |

### Error Response Schema
```json
{
  "success": false,
  "error": "string — short code identifying the error category",
  "details": [
    "field_name -> Human-readable explanation of the specific failure"
  ]
}
```

---

## 6. OpenAPI / Swagger Tagging & Organization

| Tag          | Endpoints                                                                     |
|--------------|-------------------------------------------------------------------------------|
| `Links`      | `POST /api/v1/links`, `GET /api/v1/links`, `GET /api/v1/links/{code}`, `DELETE /api/v1/links/{code}` |
| `Inspection` | `POST /api/v1/links/{code}/inspect`                                           |
| `Redirect`   | `GET /{code}`                                                                 |

Tags are defined in `main.py` via FastAPI `tags_metadata` and declared on each router.  
The `/api/v1/links/{code}/inspect` endpoint carries **both** the `Links` and `Inspection` tags to make it discoverable from both perspectives in the interactive docs.

---

## Change Log
| Version | Date       | Change                                                                          |
|---------|------------|---------------------------------------------------------------------------------|
| 0.1     | 2025-05-22 | Initial API design — 5 endpoints covering all job stories                       |
| 0.2     | 2025-05-22 | Removed pagination entirely — flat array response, no `meta` envelope           |
