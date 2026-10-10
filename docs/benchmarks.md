# Performance Benchmarks — FastURL
_Last updated: 2026-10-10_

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
| Machine           | Apple MacBook Pro M5 Max (6 performance + 12 efficiency cores) |
| RAM               | 36 GB                          |
| Storage           | 2 TB NVMe SSD                  |
| OS                | macOS 27.0.1 (Darwin arm64)    |
| Python            | 3.14 (from `.python-version`)  |
| ASGI server       | Uvicorn (`uvicorn[standard]`)  |
| Workers           | Run 1: 1 — Run 2: 1 and 4      |
| Database          | Run 1: SQLite via `aiosqlite` — Run 2: PostgreSQL 17.11 (Homebrew, local, default settings) via `asyncpg` |
| Load generator    | `hey`, on the same machine as server and database |

> **Why 1 worker for Run 1?** A single Uvicorn process isolates the SQLite variable and eliminates IPC overhead between workers. This is the cleanest starting point before any infrastructure change. SQLite cannot use more workers anyway (database-wide write lock).
>
> **Why 1 and 4 workers for Run 2?** Switching to PostgreSQL changes two things at once: the database engine and the possibility of running several workers. Running PostgreSQL with 1 worker isolates the database effect; 4 workers then measure the worker effect.
>
> **Shared machine.** `hey`, the Uvicorn workers and PostgreSQL all compete for the same CPU cores, so absolute numbers are lower than on separate hosts. Comparisons between runs remain valid because the setup is identical.

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
The same flags are kept in every run so results stay comparable.

**PostgreSQL connection pool sizing.** Each Uvicorn worker is a separate process with its own connection pool.
`hey -c N` keeps N requests in flight, spread across the workers, and each in-flight request holds one connection.
Two rules keep the pool from becoming the bottleneck (or failing):

| Rule | Why |
|------|-----|
| `pool_size ≥ c ÷ workers` | Otherwise excess requests queue for a free connection and the wait shows up as latency — the pool is measured, not the database |
| `workers × (pool_size + max_overflow) < max_connections` (97 usable by non-superusers with the default 100) | Otherwise PostgreSQL rejects connections and requests fail with HTTP 500 (`TooManyConnectionsError`) |

`max_overflow: 0` keeps the pool fixed, so no connection is opened or closed during a run.

| Workers | `-c` | `pool_size` | `max_overflow` | Total connections |
|---------|------|-------------|----------------|-------------------|
| 1       | 50   | 50          | 0              | 50                |
| 4       | 50   | 15          | 0              | 60                |

### 3.3 Warm-up

Before each official run, execute one warm-up pass and discard the results.
The warm-up uses the **same concurrency as the official run** (`-n 2000 -c 50` for reads/redirects, `-n 100 -c 5` for writes):

```bash
hey -n 2000 -c 50 -disable-redirects http://127.0.0.1:8000/<code>
```

This flushes SQLAlchemy's connection pool initialisation and any OS-level TCP setup overhead from the measurement window.
Connections are opened lazily, so a warm-up at lower concurrency (Run 1 used `-n 500 -c 10`) leaves part of the pool to be opened during the official run — negligible with SQLite, but measurable with a PostgreSQL pool of 15–50 connections per worker.

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

### 4.2 Prepare PostgreSQL (Run 2 onwards)

```bash
# Start PostgreSQL (Homebrew, not registered as a service)
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /opt/homebrew/var/postgresql@17 -l /opt/homebrew/var/postgresql@17/server.log start

# Create user and database (once); use the same password as DATABASE__POSTGRESQL__PASSWORD in .env
/opt/homebrew/opt/postgresql@17/bin/psql -d postgres -v password='...' -f sql/postgres/01-init-user.sql
```

The `links` table is created by the application at startup. In `config.yaml`, keep the `postgresql:` section active
(and `sqlite:` commented out) and set `app.workers` and `postgresql.pool_size` as in section 3.2.

### 4.3 Start the server

```bash
./app.sh
```

`app.sh` reads host, port and workers from `config.yaml` and prints the effective configuration
(database, pool, total connections, log level) before Uvicorn starts — check it before every run.

> Set log level to `WARNING` in `config.yaml` before starting to avoid Loguru I/O overhead on every request distorting the results:
> ```yaml
> log:
>   level: WARNING
> ```

### 4.4 Pre-seed the database

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

Replace `<code>` with the value obtained in section 4.4.

### 5.1 `GET /{code}` — Public redirect (hot path)

> Note: `-disable-redirects` is required so `hey` measures FastURL's `307 Temporary Redirect` response without following the redirect to the target website.

```bash
# Warm-up (discard results)
hey -n 2000 -c 50 -disable-redirects http://127.0.0.1:8000/<code>

# Official run
hey -n 10000 -c 50 -disable-redirects http://127.0.0.1:8000/<code>
```

### 5.2 `GET /api/v1/links/{code}` — Read link details

```bash
# Warm-up (discard results)
hey -n 2000 -c 50 http://127.0.0.1:8000/api/v1/links/<code>

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

**Expected ranges (M5 Max, 1 worker):**

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

### 6.2 Run 2 — PostgreSQL migration (1 and 4 Uvicorn workers) — issues #2, #3

_Date: 2026-10-10_
_Commit: c8de56b + uncommitted PostgreSQL support changes_
_Database: PostgreSQL 17.11, local, default settings (`max_connections = 100`)_
_DB size: small; not reset between configurations — each `POST` run adds ~1,100 rows. Lookups use the unique index on `code`, so table size does not affect read/redirect results at this scale._

| Configuration         | `app.workers` | `pool_size` | `max_overflow` | Total connections |
|-----------------------|---------------|-------------|----------------|-------------------|
| PostgreSQL, 1 worker  | 1             | 50          | 0              | 50                |
| PostgreSQL, 4 workers | 4             | 15          | 0              | 60                |

**Results**

| Endpoint                    | Configuration         | req/s    | p50     | p95      | p99      | Errors |
|-----------------------------|-----------------------|----------|---------|----------|----------|--------|
| `GET /{code}`               | SQLite, 1 worker (Run 1) | 747.80   | 65.0 ms | 103.9 ms | 132.8 ms | 0.0% |
|                             | PostgreSQL, 1 worker  | 997.98   | 21.1 ms | 148.9 ms | 247.8 ms | 0.0%   |
|                             | PostgreSQL, 4 workers | 1,542.04 | 30.1 ms | 55.9 ms  | 73.9 ms  | 0.0%   |
| `GET /api/v1/links/{code}`  | SQLite, 1 worker (Run 1) | 1,421.72 | 34.3 ms | 52.7 ms | 64.3 ms | 0.0% |
|                             | PostgreSQL, 1 worker  | 1,835.81 | 26.8 ms | 29.1 ms  | 47.2 ms  | 0.0%   |
|                             | PostgreSQL, 4 workers | 4,696.43 | 10.4 ms | 12.1 ms  | 13.7 ms  | 0.0%   |
| `POST /api/v1/links`        | SQLite, 1 worker (Run 1) | 286.56 | 14.1 ms | 94.1 ms  | 456.3 ms | 0.0% |
|                             | PostgreSQL, 1 worker  | 383.08   | 25.0 ms | 34.4 ms  | 49.7 ms  | 0.0%   |
|                             | PostgreSQL, 4 workers | 848.30   | 8.0 ms  | 22.3 ms  | 54.6 ms  | 0.0%   |

**Throughput breakdown — database effect vs worker effect**

| Endpoint                    | Database effect (SQLite → PostgreSQL, 1 worker) | Worker effect (PostgreSQL 1 → 4 workers) | Total (Run 1 → Run 2, 4 workers) |
|-----------------------------|------------------|------------------|-------|
| `GET /{code}`               | +33%             | 1.55×            | 2.06× |
| `GET /api/v1/links/{code}`  | +29%             | 2.56×            | 3.30× |
| `POST /api/v1/links`        | +34%             | 2.21×            | 2.96× |

**Observations:**
- **The database alone is worth ~+30% throughput**, remarkably consistent across all three endpoints (+29% to +34% at 1 worker).
- **Most of the gain comes from the workers**, which PostgreSQL makes possible (SQLite is limited to 1 worker). Pure reads scale best: 2.56× with 4 workers out of a theoretical 4×, with `hey` and PostgreSQL sharing the same CPU.
- **Write tail latency is the clearest win.** `POST` p99 drops from 456.3 ms (SQLite) to 49.7 ms with PostgreSQL at 1 worker: SQLite serialises every write behind a database-wide lock, PostgreSQL commits concurrent transactions in parallel.
- **The click counter is the new bottleneck.** Every redirect runs `UPDATE links SET clicks_count = clicks_count + 1` on the *same row*. PostgreSQL queues concurrent updates of one row behind each other's commit (row lock), so:
  - at 1 worker the redirect has a better median than SQLite (21.1 ms vs 65.0 ms) but **worse tail latency** (p99 247.8 ms vs 132.8 ms) — with a 50-connection pool, up to 50 updates queue on the same row;
  - the redirect is the endpoint that scales worst with workers (1.55× vs 2.56× for pure reads).
  
  The read endpoint on the same configuration has a tight tail (p95 29.1 ms vs 148.9 ms for the redirect), which isolates the row update as the cause. This is the motivation for the planned write-behind click counter.
- **`POST` median at 1 worker (25.0 ms) is worse than SQLite (14.1 ms)** but drops to 8.0 ms with 4 workers: the cost is the 10 concurrent requests queuing on a single Python process, not the PostgreSQL round-trip.
- **Click counts are exact under concurrency:** after the 4-worker redirect warm-up and official run (2,000 + 10,000 requests), `clicks_count` was exactly 12,000.
- **`POST` depends on an external site.** Each created link schedules a background inspection: an HTTP request to `https://www.example.com` followed by an `UPDATE`. Write results therefore include network variability and are less stable than read results. This applies to Run 1 as well, so the comparison holds.
- **Pool sizing matters.** A first exploratory run with 4 workers and the initial pool (`pool_size: 20`, `max_overflow: 10` → up to 120 connections) produced HTTP 500 errors (`TooManyConnectionsError`) once PostgreSQL's 97 usable connections were exhausted. See section 3.2 for the sizing rules.

---

### 6.3 Roadmap — Runs 3 to 5 _(planned)_

**Target.** The reference capacity estimate for a URL shortener (500M new URLs/month, 100:1 read/write ratio) is
**~200 creations/s** and **~20,000 redirects/s**. After Run 2, creations are already above target (848 req/s with
4 workers), while redirects are ~13× below it (1,542 req/s). The next runs change **one variable at a time** to
show which change moves the redirect hot path, and by how much.

| Run | Change | Variable isolated | Hypothesis (to be verified) |
|-----|--------|-------------------|-----------------------------|
| 3   | PostgreSQL with 8 and 12 workers | Number of workers | Reads keep scaling, sub-linearly (18 cores shared with `hey` and PostgreSQL; gains likely flatten past the 6 performance cores). Redirects barely move: the bottleneck is the row-lock queue on `clicks_count`, not CPU, and more workers make the queue longer. |
| 4   | + Redis cache of `code → target_url` (best worker count from Run 3) | DB read on the redirect path | Modest redirect gain: the PostgreSQL lookup disappears, but the per-redirect `UPDATE` remains. |
| 5   | + write-behind click counter (Redis `INCR`, periodic flush to PostgreSQL) | DB write on the redirect path | The large step: the redirect becomes a Redis read + `INCR`, so it should approach (or exceed) the pure-read endpoint. |

#### Run 3 — scaling workers

Pool sizing follows section 3.2 (`pool_size ≥ c ÷ workers`, total below 97 connections):

| Workers | `-c` | Requests per worker | `pool_size` | `max_overflow` | Total connections |
|---------|------|---------------------|-------------|----------------|-------------------|
| 8       | 50   | ~6–7                | 8           | 0              | 64                |
| 12      | 50   | ~4–5                | 6           | 0              | 72                |

- With 12 workers, `-c 50` gives each worker only 4–5 concurrent requests and may not saturate them. Raising `-c`
  (e.g. 200 → ~17 per worker → 204 connections) exceeds PostgreSQL's 97 usable connections: it requires raising
  `max_connections` or adding a connection pooler (PgBouncer). If tried, record it as a separate configuration.
- Monitor CPU during the runs (`top -o cpu`). If `hey` or PostgreSQL saturate a core, the machine — not FastURL — has
  become the limit and further worker increases are not meaningful on this host.

#### Run 4 — Redis cache

- The redirect resolves `code → target_url` from Redis; on a miss it reads PostgreSQL and populates the cache.
- **Invalidation:** a deleted or expired link must be removed from Redis, otherwise it keeps redirecting. Each key
  gets a TTL no later than the link's `expires_at`.
- Keep the worker count fixed at the best value from Run 3.

#### Run 5 — write-behind click counter

- The redirect performs only a Redis read and a Redis `INCR`; a separate process periodically flushes the counters
  (and `last_clicked_at`) to PostgreSQL.
- **Trade-offs to document with the results:**
  - `clicks_count` in PostgreSQL lags the real count by up to one flush interval (eventual consistency).
  - If Redis fails before a flush, the clicks counted since the last flush are lost — usually acceptable for
    analytics, but it is a deliberate choice.

#### Protocol for every run

- Same machine, same `hey` parameters and warm-up as Runs 1–2 (sections 3.2–3.3).
- Always measure **both** `GET /{code}` and `GET /api/v1/links/{code}`: the gap between redirect and pure read is
  what shows the cost of the redirect's database work.
- `POST /api/v1/links` is already above target; measure it again only if a change touches the write path.

#### Beyond a single machine

20,000 redirects/s is not reachable — nor measurable — on one laptop: at ~1,200 req/s per worker (pure reads) it
needs ~17–20 workers, i.e. several hosts behind a load balancer, with `hey` on a separate machine. High availability
(PostgreSQL replicas and failover, replicated Redis) and partitioning for billions of rows are out of scope for these
runs.

---

## 7. Migrating from SQLite to PostgreSQL

FastURL supports both backends; the active one is chosen in `config.yaml`. Data is **not** migrated:
PostgreSQL starts with an empty `links` table (the application creates it at startup).

### 7.1 Local (Homebrew)

1. Install and start PostgreSQL 17 (not registered as a service):
   ```bash
   brew install postgresql@17
   /opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /opt/homebrew/var/postgresql@17 -l /opt/homebrew/var/postgresql@17/server.log start
   ```
2. Choose a password and put it in `.env` (template: `.env.example`):
   ```bash
   DATABASE__POSTGRESQL__PASSWORD=...
   ```
3. Create the application user and database with the same password:
   ```bash
   /opt/homebrew/opt/postgresql@17/bin/psql -d postgres -v password='...' -f sql/postgres/01-init-user.sql
   ```
4. In `config.yaml`, comment out the `sqlite:` section and uncomment `postgresql:`.
   Set `app.workers` and `postgresql.pool_size` following section 3.2 (e.g. 4 workers, `pool_size: 15`).
5. Start with `./app.sh` and check the configuration summary (database, pool, total connections).

### 7.2 Docker Compose

```bash
docker compose up                                                       # SQLite
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up  # PostgreSQL 17
```

The PostgreSQL override starts a `postgres` service (user `fasturl_user`, database `fasturl_db`, password from
`DATABASE__POSTGRESQL__PASSWORD` in `.env`) and points the API to it. The `postgresql:` section must be active in
`config.yaml`; if `sqlite:` is still active, startup fails with "configure only one database backend".

### 7.3 Running the test suite against PostgreSQL

Integration tests use in-memory SQLite by default. To run them against PostgreSQL, create a dedicated test database
(tables are created and dropped around every test) and set `TEST_DATABASE_URL`:

```bash
/opt/homebrew/opt/postgresql@17/bin/psql -d postgres -c "CREATE DATABASE fasturl_test OWNER fasturl_user"
TEST_DATABASE_URL="postgresql+asyncpg://fasturl_user:<password>@127.0.0.1:5432/fasturl_test" uv run pytest
```

### 7.4 Schema differences

| Column              | SQLite                         | PostgreSQL                         |
|---------------------|--------------------------------|------------------------------------|
| `id`                | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY`          |
| `is_active`         | `BOOLEAN` (stored as 0/1)      | native `BOOLEAN`                   |
| `inspection_status` | `VARCHAR` + `CHECK` constraint | native `ENUM inspection_status`    |
| `latency_ms`        | `REAL`                         | `DOUBLE PRECISION`                 |

Reference DDL: `sql/sqlite/schema.sql`, `sql/postgres/02-schema.sql`. All timestamps are stored as naive UTC
(`TIMESTAMP WITHOUT TIME ZONE`), independent of the PostgreSQL server timezone.

> **Existing PostgreSQL databases.** `create_all` creates missing tables but never alters existing ones. A `links`
> table created before `inspection_status` became an `ENUM` keeps its `VARCHAR` column; drop it
> (`DROP TABLE links;`) and restart the application to recreate it.

---

## 8. Change Log

| Version | Date       | Change                                                             |
|---------|------------|--------------------------------------------------------------------|
| 0.1     | 2025-06-01 | Initial document — methodology, pre-conditions, commands, Run 1 skeleton |
| 0.2     | 2026-10-08 | Added `-disable-redirects` note; executed and recorded Run 1 SQLite baseline results |
| 0.3     | 2026-10-10 | Recorded Run 2 (PostgreSQL, 1 and 4 workers) with database vs worker breakdown; added pool sizing rules; warm-up at official-run concurrency; PostgreSQL pre-conditions; `./app.sh` start; corrected machine to M5 Max and Python to 3.14 |
| 0.4     | 2026-10-10 | Added section 7, migrating from SQLite to PostgreSQL (local, Docker Compose, tests, schema differences) |
| 0.5     | 2026-10-10 | Section 6.3: roadmap for Runs 3–5 (worker scaling, Redis cache, write-behind click counter) with hypotheses, pool sizing and protocol |
