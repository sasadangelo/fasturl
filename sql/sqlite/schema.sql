-- -----------------------------------------------------------------------------
-- FastURL — SQLite Schema
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(16) NOT NULL,
    target_url TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    expires_at TIMESTAMP NULL DEFAULT NULL,
    inspection_status VARCHAR(16) NOT NULL DEFAULT 'pending_analysis'
        CHECK (inspection_status IN ('pending_analysis', 'active', 'unreachable')),
    http_status_code INTEGER NULL DEFAULT NULL,
    latency_ms REAL NULL DEFAULT NULL,
    title TEXT NULL DEFAULT NULL,
    description TEXT NULL DEFAULT NULL,
    image_url TEXT NULL DEFAULT NULL,
    last_checked_at TIMESTAMP NULL DEFAULT NULL,
    clicks_count INTEGER NOT NULL DEFAULT 0,
    last_clicked_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_links_code ON links(code);
