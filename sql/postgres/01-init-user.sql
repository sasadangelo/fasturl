-- -----------------------------------------------------------------------------
-- FastURL — PostgreSQL User & Database Initialization (Run as postgres admin)
--
-- The password is not stored here: pass it as a psql variable, using the same
-- value as DATABASE__POSTGRESQL__PASSWORD in .env:
--
--   psql -d postgres -v password='...' -f sql/postgres/01-init-user.sql
-- -----------------------------------------------------------------------------

\set ON_ERROR_STOP on

\if :{?password}
\else
   DO $$ BEGIN RAISE EXCEPTION 'missing password. Usage: psql -d postgres -v password=... -f sql/postgres/01-init-user.sql'; END $$;
\endif

-- 1. Create dedicated application user if it does not exist
SELECT format('CREATE ROLE fasturl_user WITH LOGIN PASSWORD %L', :'password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'fasturl_user')\gexec

-- 2. Create application database owned by the application user
SELECT 'CREATE DATABASE fasturl_db OWNER fasturl_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'fasturl_db')\gexec

-- 3. Connect to fasturl_db and configure schema permissions
\connect fasturl_db

-- Grant schema privileges
GRANT CONNECT ON DATABASE fasturl_db TO fasturl_user;
GRANT ALL ON SCHEMA public TO fasturl_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fasturl_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fasturl_user;

-- Ensure future tables and sequences created by any user in schema public are accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO fasturl_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO fasturl_user;
