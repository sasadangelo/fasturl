-- -----------------------------------------------------------------------------
-- FastURL — PostgreSQL DDL Schema
-- -----------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_type WHERE typname = 'inspection_status') THEN
        CREATE TYPE inspection_status AS ENUM ('pending_analysis', 'active', 'unreachable');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS links (
    id SERIAL PRIMARY KEY,
    code VARCHAR(16) NOT NULL,
    target_url TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMP NULL DEFAULT NULL,
    inspection_status inspection_status NOT NULL DEFAULT 'pending_analysis',
    http_status_code INTEGER NULL DEFAULT NULL,
    latency_ms DOUBLE PRECISION NULL DEFAULT NULL,
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
