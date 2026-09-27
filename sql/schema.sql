-- =============================================================================
-- Schema: FastURL
-- Engine: SQLite (via SQLAlchemy async + aiosqlite)
-- Created: 2025-05-15
-- Last modified: 2025-05-15
-- =============================================================================

-- links: shortened URL aggregate — owns ShortCode, TargetUrl, LinkMetrics,
--        and LinkInspection value objects as embedded columns.
-- Last modified: 2025-05-15
CREATE TABLE IF NOT EXISTS links (
    -- Internal surrogate PK (never exposed via API)
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- External identifier (UUID stored as TEXT — exposed in API responses)
    public_id       TEXT    NOT NULL,

    -- ShortCode VO: Base62 alphanumeric, 7–16 characters
    code            TEXT    NOT NULL,

    -- TargetUrl VO: validated HTTP/HTTPS destination URL
    target_url      TEXT    NOT NULL,

    -- Operational state (soft-delete / disable)
    is_active       INTEGER NOT NULL DEFAULT 1,

    -- Expiration (NULL = never expires; lazy-checked on redirect)
    expires_at      TEXT    NULL,

    -- LinkInspection VO
    inspection_status   TEXT    NOT NULL DEFAULT 'pending_analysis',
    http_status_code    INTEGER NULL,
    latency_ms          REAL    NULL,
    title               TEXT    NULL,
    description         TEXT    NULL,
    image_url           TEXT    NULL,
    last_checked_at     TEXT    NULL,

    -- LinkMetrics VO
    clicks_count        INTEGER NOT NULL DEFAULT 0,
    last_clicked_at     TEXT    NULL,

    -- Audit timestamps (ISO 8601 strings)
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT uq_links_public_id   UNIQUE (public_id),
    CONSTRAINT uq_links_code        UNIQUE (code),
    CONSTRAINT chk_links_code_len   CHECK  (length(code) BETWEEN 7 AND 16),
    CONSTRAINT chk_links_is_active  CHECK  (is_active IN (0, 1)),
    CONSTRAINT chk_links_clicks     CHECK  (clicks_count >= 0),
    CONSTRAINT chk_links_insp_status CHECK (
        inspection_status IN ('pending_analysis', 'active', 'unreachable')
    )
);

-- Indexes after all CREATE TABLE statements

-- Primary query paths:
--   GET /{code}            → lookup by code (redirect path, hot)
--   GET /api/v1/links/{code} → lookup by code (management API)
--   GET /api/v1/links/     → list all (scan, no index needed)
CREATE INDEX IF NOT EXISTS idx_links_code       ON links (code);
CREATE INDEX IF NOT EXISTS idx_links_public_id  ON links (public_id);

-- Useful for listing only active links or filtering by expiry
CREATE INDEX IF NOT EXISTS idx_links_is_active  ON links (is_active);

-- End of schema
