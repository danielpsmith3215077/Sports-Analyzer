-- supabase/schema.sql
-- Canonical PostgreSQL schema for the Sports Analyzer SaaS (Supabase cluster).
-- Idempotent: safe to run repeatedly. Mirrored by backend/db.py SCHEMA_STATEMENTS
-- and applied automatically by backend/init_db.py on migration.

-- ---------------------------------------------------------------------------
-- User profiles / licensing
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                   TEXT PRIMARY KEY,
    email                TEXT NOT NULL UNIQUE,
    name                 TEXT,
    plan_type            TEXT NOT NULL DEFAULT 'individual'
                             CHECK (plan_type IN ('individual','enterprise')),
    access_token         TEXT NOT NULL UNIQUE,
    stripe_customer_id   TEXT,
    parent_enterprise_id TEXT REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at           TIMESTAMPTZ NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active','paused','expired','revoked'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_access_token ON users (access_token);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);
CREATE INDEX IF NOT EXISTS idx_users_parent ON users (parent_enterprise_id);
CREATE INDEX IF NOT EXISTS idx_users_stripe_cust ON users (stripe_customer_id);

-- ---------------------------------------------------------------------------
-- Stripe payment webhook events (audit log)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stripe_webhook_events (
    id                 TEXT PRIMARY KEY,
    event_id           TEXT UNIQUE,
    event_type         TEXT NOT NULL,
    stripe_customer_id TEXT,
    user_id            TEXT REFERENCES users(id),
    payload            JSONB,
    received_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhook_event_type ON stripe_webhook_events (event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_customer ON stripe_webhook_events (stripe_customer_id);

-- ---------------------------------------------------------------------------
-- Match telemetry analytics logs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_telemetry (
    id               TEXT PRIMARY KEY,
    user_id          TEXT REFERENCES users(id),
    event_name       TEXT NOT NULL,
    fighter_a        TEXT,
    fighter_b        TEXT,
    predicted_winner TEXT,
    confidence       DOUBLE PRECISION,
    metadata         JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_created ON match_telemetry (created_at);
CREATE INDEX IF NOT EXISTS idx_telemetry_user ON match_telemetry (user_id);
