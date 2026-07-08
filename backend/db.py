"""
backend/db.py
Async, cloud-native data-access layer for the Sports Analyzer SaaS.

PostgreSQL / Supabase ONLY. The previous local SQLite fallback (and its file
locks) has been removed as part of the Multi-Cloud migration — the FastAPI
engine now runs as a long-running Render Web Service that talks to a remote
Supabase Postgres cluster via `DATABASE_URL`.

All identity/time values (UUID id, access_token, created_at, expires_at,
default status) are generated in the application layer; the Postgres DDL below
(mirrored in supabase/schema.sql) also declares matching defaults as a
defense-in-depth safety net and is applied idempotently on startup.
"""

import os
import secrets
import uuid
from datetime import datetime, timezone

from databases import Database
from dateutil.relativedelta import relativedelta

# ---------------------------------------------------------------------------
# Configuration — Postgres/Supabase only
# ---------------------------------------------------------------------------
LICENSE_MONTHS = 6

# Markers that indicate an unconfigured / template connection string.
_PLACEHOLDER_MARKERS = (
    "YOUR_PROJECT_REF",
    "PASTE_YOUR",
    "PASTE_YOUR_SUPABASE_CONNECTION_STRING_HERE",
    "changeme",
    "<",
)


def _normalize_db_url(raw: str) -> str:
    """Normalize a Supabase/Postgres URL to the async (asyncpg) driver form
    that the `databases` library requires."""
    raw = raw.strip().strip('"').strip("'")
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]
    return raw


def _is_placeholder(raw: str) -> bool:
    return (not raw) or any(m in raw for m in _PLACEHOLDER_MARKERS) or raw.startswith("sqlite")


# Resolve lazily so the module (and the /api/healthcheck route) can import even
# before a real DATABASE_URL is configured; connect() raises a clear error.
_RAW_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip().strip('"').strip("'")
DATABASE_URL = _normalize_db_url(_RAW_DATABASE_URL) if _RAW_DATABASE_URL else ""


def _valid_identifier(name: str) -> bool:
    import re
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name))


# Optional dedicated Postgres schema. Left unset in production (defaults to the
# standard `public` schema, behavior unchanged). Isolated test runs set
# DB_SCHEMA to a throwaway schema so they never touch production tables.
DB_SCHEMA = os.environ.get("DB_SCHEMA", "").strip() or None
if DB_SCHEMA and not _valid_identifier(DB_SCHEMA):
    raise RuntimeError(f"DB_SCHEMA must be a simple SQL identifier, got: {DB_SCHEMA!r}")


def _build_database() -> Database | None:
    """Build the Database for a well-formed, non-placeholder URL (else None)."""
    if not DATABASE_URL or _is_placeholder(_RAW_DATABASE_URL):
        return None
    options: dict = {}
    if DB_SCHEMA:
        # asyncpg applies this to every pooled connection so all DDL/DML lands
        # in the dedicated schema first, falling back to public for extensions.
        options["server_settings"] = {"search_path": f"{DB_SCHEMA},public"}
    return Database(DATABASE_URL, **options)


database: Database | None = _build_database()

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
PLAN_INDIVIDUAL = "individual"
PLAN_ENTERPRISE = "enterprise"
VALID_PLANS = {PLAN_INDIVIDUAL, PLAN_ENTERPRISE}

STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"
VALID_STATUSES = {STATUS_ACTIVE, STATUS_PAUSED, STATUS_EXPIRED, STATUS_REVOKED}

USER_COLUMNS = [
    "id", "email", "name", "plan_type", "access_token", "stripe_customer_id",
    "parent_enterprise_id", "created_at", "expires_at", "status",
]

# ---------------------------------------------------------------------------
# PostgreSQL schema (idempotent). Applied on startup and by backend/init_db.py.
# The canonical copy also lives in supabase/schema.sql for manual review.
# ---------------------------------------------------------------------------
SCHEMA_STATEMENTS: list[str] = [
    # --- user profiles ------------------------------------------------------
    """
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
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_access_token ON users (access_token);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (email);",
    "CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);",
    "CREATE INDEX IF NOT EXISTS idx_users_parent ON users (parent_enterprise_id);",
    "CREATE INDEX IF NOT EXISTS idx_users_stripe_cust ON users (stripe_customer_id);",
    # --- Stripe payment webhook events -------------------------------------
    """
    CREATE TABLE IF NOT EXISTS stripe_webhook_events (
        id                 TEXT PRIMARY KEY,
        event_id           TEXT UNIQUE,
        event_type         TEXT NOT NULL,
        stripe_customer_id TEXT,
        user_id            TEXT REFERENCES users(id),
        payload            JSONB,
        received_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_webhook_event_type ON stripe_webhook_events (event_type);",
    "CREATE INDEX IF NOT EXISTS idx_webhook_customer ON stripe_webhook_events (stripe_customer_id);",
    # --- match telemetry analytics logs ------------------------------------
    """
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_telemetry_created ON match_telemetry (created_at);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_user ON match_telemetry (user_id);",
]

# Tables the migration/verification step expects to exist afterwards.
EXPECTED_TABLES = ("users", "stripe_webhook_events", "match_telemetry")


# ---------------------------------------------------------------------------
# Time / identity helpers
# ---------------------------------------------------------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def default_expiry(created: datetime | None = None) -> datetime:
    return (created or now_utc()) + relativedelta(months=LICENSE_MONTHS)


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def new_uuid() -> str:
    return str(uuid.uuid4())


def parse_dt(value) -> datetime:
    """Normalize a timestamp to a tz-aware UTC datetime (asyncpg returns
    datetime objects; ISO strings are tolerated for safety)."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def days_remaining(expires_at) -> int:
    delta = parse_dt(expires_at) - now_utc()
    secs = delta.total_seconds()
    return int(secs // 86400) if secs > 0 else 0


def is_valid_row(row) -> bool:
    return row["status"] == STATUS_ACTIVE and parse_dt(row["expires_at"]) > now_utc()


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------
def _require_database() -> Database:
    if database is None:
        raise RuntimeError(
            "DATABASE_URL is not configured with a real Supabase/Postgres "
            "connection string. Set DATABASE_URL (e.g. in .env.local or the "
            "Render service env) to postgresql://<user>:<pass>@<host>:5432/postgres "
            "before connecting."
        )
    return database


async def ensure_schema() -> None:
    """Idempotently create all required Postgres tables + indexes (within
    DB_SCHEMA if configured, otherwise the default public schema)."""
    db = _require_database()
    if DB_SCHEMA:
        await db.execute(f'CREATE SCHEMA IF NOT EXISTS "{DB_SCHEMA}"')
    for statement in SCHEMA_STATEMENTS:
        await db.execute(statement)


async def verify_schema() -> dict[str, bool]:
    """Return {table_name: exists} for each expected table (via to_regclass)."""
    db = _require_database()
    schema = DB_SCHEMA or "public"
    present: dict[str, bool] = {}
    for table in EXPECTED_TABLES:
        row = await db.fetch_one(
            "SELECT to_regclass(:qualified) AS oid",
            {"qualified": f"{schema}.{table}"},
        )
        present[table] = bool(row and row["oid"] is not None)
    return present


async def connect() -> None:
    db = _require_database()
    await db.connect()
    await ensure_schema()


async def disconnect() -> None:
    if database is not None:
        await database.disconnect()


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------
_INSERT_SQL = """
INSERT INTO users (
    id, email, name, plan_type, access_token, stripe_customer_id,
    parent_enterprise_id, created_at, expires_at, status
) VALUES (
    :id, :email, :name, :plan_type, :access_token, :stripe_customer_id,
    :parent_enterprise_id, :created_at, :expires_at, :status
)
"""


async def create_user(
    email: str,
    name: str | None,
    plan_type: str = PLAN_INDIVIDUAL,
    expires_at: datetime | None = None,
    parent_enterprise_id: str | None = None,
    stripe_customer_id: str | None = None,
    status: str = STATUS_ACTIVE,
    access_token: str | None = None,
) -> dict:
    db = _require_database()
    created = now_utc()
    expires = expires_at or default_expiry(created)
    uid = new_uuid()
    values = {
        "id": uid,
        "email": email,
        "name": name,
        "plan_type": plan_type,
        "access_token": access_token or generate_access_token(),
        "stripe_customer_id": stripe_customer_id,
        "parent_enterprise_id": parent_enterprise_id,
        "created_at": created,
        "expires_at": expires,
        "status": status,
    }
    await db.execute(_INSERT_SQL, values)
    return await get_user(uid)


async def list_users() -> list[dict]:
    db = _require_database()
    rows = await db.fetch_all("SELECT * FROM users ORDER BY created_at ASC")
    return [dict(r) for r in rows]


async def get_user(user_id: str) -> dict | None:
    db = _require_database()
    row = await db.fetch_one(
        "SELECT * FROM users WHERE id = :id", {"id": user_id}
    )
    return dict(row) if row else None


async def get_user_by_token(access_token: str) -> dict | None:
    db = _require_database()
    row = await db.fetch_one(
        "SELECT * FROM users WHERE access_token = :t", {"t": access_token}
    )
    return dict(row) if row else None


async def get_user_by_email(email: str) -> dict | None:
    db = _require_database()
    row = await db.fetch_one(
        "SELECT * FROM users WHERE email = :e", {"e": email}
    )
    return dict(row) if row else None


async def get_user_by_stripe_customer(customer_id: str) -> dict | None:
    db = _require_database()
    row = await db.fetch_one(
        "SELECT * FROM users WHERE stripe_customer_id = :c", {"c": customer_id}
    )
    return dict(row) if row else None


async def update_status(user_id: str, status: str) -> dict | None:
    db = _require_database()
    await db.execute(
        "UPDATE users SET status = :s WHERE id = :id",
        {"s": status, "id": user_id},
    )
    return await get_user(user_id)


# ---------------------------------------------------------------------------
# Auxiliary logging helpers (Stripe webhook audit + match telemetry)
# ---------------------------------------------------------------------------
async def record_webhook_event(
    event_type: str,
    event_id: str | None = None,
    stripe_customer_id: str | None = None,
    user_id: str | None = None,
    payload: str | None = None,
) -> None:
    db = _require_database()
    await db.execute(
        """
        INSERT INTO stripe_webhook_events (id, event_id, event_type,
            stripe_customer_id, user_id, payload)
        VALUES (:id, :event_id, :event_type, :stripe_customer_id, :user_id,
            CAST(:payload AS JSONB))
        ON CONFLICT (event_id) DO NOTHING
        """,
        {
            "id": new_uuid(),
            "event_id": event_id,
            "event_type": event_type,
            "stripe_customer_id": stripe_customer_id,
            "user_id": user_id,
            "payload": payload,
        },
    )


async def log_match_telemetry(
    event_name: str,
    user_id: str | None = None,
    fighter_a: str | None = None,
    fighter_b: str | None = None,
    predicted_winner: str | None = None,
    confidence: float | None = None,
    metadata: str | None = None,
) -> None:
    db = _require_database()
    await db.execute(
        """
        INSERT INTO match_telemetry (id, user_id, event_name, fighter_a,
            fighter_b, predicted_winner, confidence, metadata)
        VALUES (:id, :user_id, :event_name, :fighter_a, :fighter_b,
            :predicted_winner, :confidence, CAST(:metadata AS JSONB))
        """,
        {
            "id": new_uuid(),
            "user_id": user_id,
            "event_name": event_name,
            "fighter_a": fighter_a,
            "fighter_b": fighter_b,
            "predicted_winner": predicted_winner,
            "confidence": confidence,
            "metadata": metadata,
        },
    )
