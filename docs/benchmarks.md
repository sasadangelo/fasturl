# Performance Benchmarks — FastURL
_Last updated: 2025-06-01_

## 1. Objective

Establish the performance ceiling of FastURL at each significant infrastructure milestone.
Each run provides a documented baseline against which future optimisations (PostgreSQL migration, Redis cache, write-behind click counter) are measured.

This document covers **performance benchmarks only** — fixed load, fixed duration, measuring throughput and latency percentiles.
It is not a stress test (finding the break point) nor a load test (validating SLOs under sustained production load).
See `docs/test-strategy.md` section 3.3 for the full classification rationale.

---

## 2. Test Environment

| Attribute         | Value                          |
|-------------------|--------------------------------|
| Machine           | Apple MacBook Pro M4 Pro        |
| RAM               | 36 GB                          |
| Storage           | 2 TB NVMe SSD                  |
| OS                | macOS (Darwin arm64)           |
| Python            | 3.12 (from `.python-version`)  |
| ASGI server       | Uvicorn (`uvicorn[standard]`)  |
| Workers           | 1 (single process)             |
| Database          | SQLite via `aiosqlite`         |
| Load generator    | `hey`                          |

> **Why 1 worker?** A single Uvicorn process isolates the SQLite variable and eliminates IPC overhead between workers. This is the cleanest starting point before any infrastructure change.

---

## 3. Methodology

### 3.1 Tool

[`hey`](https://github.com/rakyll/hey) — a lightweight HTTP load generator written in Go.

**Installation:**
```bash
brew install hey
```

**Verify:**
```bash
hey --version
```

### 3.2 Load Parameters

| Endpoint type | Flags             | Rationale |
|---------------|-------------------|-----------|
| Read / redirect | `-n 10000 -c 50` | 10 000 requests at 50 concurrent connections — saturates the event loop without triggering `SQLITE_BUSY` errors |
| Write (create)  | `-n 1000 -c 10`  | Conservative: each POST performs a synchronous INSERT + commit + Base62 generation |

`-c 50` is chosen deliberately — higher concurrency on a 1-worker SQLite setup produces `SQLITE_BUSY` errors that pollute the baseline with artificial failures rather than measuring real throughput.

### 3.3 Warm-up

Before each official run, execute one warm-up pass with reduced load and discard the results:

```bash
hey -n 500 -c 10 http://127.0.0.1:8000/<code>
```

This flushes SQLAlchemy's connection pool initialisation and any OS-level TCP setup overhead from the measurement window.

### 3.4 Metrics Recorded

| Metric  | Description |
|---------|-------------|
| req/s   | Requests per second (throughput) |
| p50     | Median latency — typical user experience |
| p95     | 95th percentile latency — most users |
| p99     | 99th percentile latency — tail latency, reveals write lock contention |
| Errors  | Percentage of non-2xx/3xx responses |

> **Do not use average latency as the primary metric.** SQLite write lock contention produces latency spikes that the mean conceals but p95/p99 expose clearly.

---

## 4. Pre-conditions

All steps below must be completed before running any benchmark.

### 4.1 Install hey

```bash
brew install hey
```

### 4.2 Start the server

```bash
uv run uvicorn fasturl.main:app --workers 1 --host 127.0.0.1 --port 8000
```

> Set log level to `WARNING` in `config.yaml` before starting to avoid Loguru I/O overhead on every request distorting the results:
> ```yaml
> log:
>   level: WARNING
> ```

### 4.3 Pre-seed the database

A test link must exist before running `GET /{code}` or `GET /api/v1/links/{code}`.
Create one via the API and note the returned `code`:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/links \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://www.example.com"}' | python3 -m json.tool
```

The response will contain a `code` field (e.g. `aB3x9zK`). Use that value in the commands below.

---

## 5. Benchmark Commands

Replace `<code>` with the value obtained in section 4.3.

### 5.1 `GET /{code}` — Public redirect (hot path)

> Note: `-disable-redirects` is required so `hey` measures FastURL's `307 Temporary Redirect` response without following the redirect to the target website.

```bash
# Warm-up (discard results)
hey -n 500 -c 10 -disable-redirects http://127.0.0.1:8000/<code>

# Official run
hey -n 10000 -c 50 -disable-redirects http://127.0.0.1:8000/<code>
```

### 5.2 `GET /api/v1/links/{code}` — Read link details

```bash
# Warm-up (discard results)
hey -n 500 -c 10 http://127.0.0.1:8000/api/v1/links/<code>

# Official run
hey -n 10000 -c 50 http://127.0.0.1:8000/api/v1/links/<code>
```

### 5.3 `POST /api/v1/links` — Create short link

```bash
# Warm-up (discard results)
hey -n 100 -c 5 -m POST \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://www.example.com"}' \
  http://127.0.0.1:8000/api/v1/links

# Official run
hey -n 1000 -c 10 -m POST \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://www.example.com"}' \
  http://127.0.0.1:8000/api/v1/links
```

---

## 6. Results

### 6.1 Run 1 — SQLite baseline (1 Uvicorn worker)

_Date: 2026-10-08_
_Commit: 91438d0_
_DB size at start: 5 rows_

| Endpoint                    | req/s    | p50     | p95     | p99     | Errors |
|-----------------------------|----------|---------|---------|---------|--------|
| `GET /{code}`               | 747.80   | 65.0 ms | 103.9 ms| 132.8 ms| 0.0%   |
| `GET /api/v1/links/{code}`  | 1,421.72 | 34.3 ms | 52.7 ms | 64.3 ms | 0.0%   |
| `POST /api/v1/links`        | 286.56   | 14.1 ms | 94.1 ms | 456.3 ms| 0.0%   |

**Expected ranges (M4 Pro, 1 worker):**

| Endpoint                    | req/s expected  | Key bottleneck |
|-----------------------------|-----------------|----------------|
| `GET /{code}`               | 4 000 – 7 000   | SQLite write lock on background `increment_clicks` |
| `GET /api/v1/links/{code}`  | 8 000 – 15 000  | Pure SELECT, no write contention |
| `POST /api/v1/links`        | 800 – 2 000     | Synchronous INSERT + commit + Base62 generation |

**Observations:**
- **Read performance (`GET /api/v1/links/{code}`)**: Yields the highest throughput (~1,422 req/s) and lowest latency (p50 of 34.3 ms, p99 of 64.3 ms) with 0 errors, acting as a baseline for non-locking read operations.
- **Redirect hot path (`GET /{code}`)**: Achieves ~748 req/s with median latency of 65.0 ms. Throughput is halved compared to pure reads because each redirect triggers background tasks / click metric increments, causing SQLite write locks.
- **Write performance (`POST /api/v1/links`)**: Achieves ~287 req/s with a p50 of 14.1 ms and p99 reaching 456.3 ms. Write serialization and transactional commits on SQLite under concurrency cause noticeable tail latency spikes.
- **Redirects in `hey`**: The `-disable-redirects` flag is essential for benchmarking `GET /{code}` so the load generator measures the HTTP 307 response directly without following external URLs.

---

### 6.2 Run 2 — PostgreSQL migration _(planned — issue #2)_

_Results to be recorded after the PostgreSQL migration milestone._

---

### 6.3 Run 3 — PostgreSQL + Redis cache _(planned — issue #3)_

_Results to be recorded after the Redis cache milestone._

---

## 7. Change Log

| Version | Date       | Change                                                             |
|---------|------------|--------------------------------------------------------------------|
| 0.1     | 2025-06-01 | Initial document — methodology, pre-conditions, commands, Run 1 skeleton |
| 0.2     | 2026-10-08 | Added `-disable-redirects` note; executed and recorded Run 1 SQLite baseline results |
