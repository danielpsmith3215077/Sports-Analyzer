"""
backend/test_backend.py
End-to-end tests for the async, Supabase/Postgres Cloud Core API.

The local SQLite fallback has been removed, so these tests now require a real
Postgres database supplied via the TEST_DATABASE_URL environment variable. When
TEST_DATABASE_URL is unset the whole module is SKIPPED (never failed), so a
plain `pytest` run stays green without cloud credentials.

Isolation: every run happens inside a throwaway Postgres schema (DB_SCHEMA)
that is created on setup and dropped (CASCADE) on teardown, so production
`public` tables are never touched.

Run:
    TEST_DATABASE_URL="postgresql://user:pass@host:5432/dbname" pytest backend/test_backend.py
"""

import asyncio
import os
import sys
from datetime import timedelta

import pytest

# ---------------------------------------------------------------------------
# SAFETY GUARD: never allow this suite to run against the live Supabase
# production project, under any variable name. This is a hard stop (not a
# skip) so a misconfigured TEST_DATABASE_URL can never write throwaway test
# rows — or worse, DROP SCHEMA CASCADE — against real user accounts, Stripe
# webhook logs, or match telemetry.
# ---------------------------------------------------------------------------
_LIVE_SUPABASE_PROJECT_REF = "cstgtdzdikfploisovdl"
for _env_name in ("TEST_DATABASE_URL", "DATABASE_URL"):
    if _LIVE_SUPABASE_PROJECT_REF in os.environ.get(_env_name, ""):
        pytest.exit(
            f"REFUSING TO RUN: {_env_name} points at the LIVE Supabase project "
            f"({_LIVE_SUPABASE_PROJECT_REF}). These tests create/drop tables and "
            f"must only ever run against an isolated, disposable test database. "
            f"Point TEST_DATABASE_URL at a separate Postgres instance/project.",
            returncode=1,
        )

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()

if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set — skipping Postgres-backed backend tests. "
        "Set it to an isolated Postgres/Supabase database to run them.",
        allow_module_level=True,
    )

# Dedicated throwaway schema for this module's run.
TEST_SCHEMA = "sa_test_backend"

# Point the app at the test database + isolated schema BEFORE importing backend.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DB_SCHEMA"] = TEST_SCHEMA

import asyncpg  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import db  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Raw asyncpg helpers (schema lifecycle + direct row edits)
# ---------------------------------------------------------------------------
def _asyncpg_dsn() -> str:
    """asyncpg wants a plain postgres DSN (no SQLAlchemy '+asyncpg' suffix)."""
    dsn = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    return dsn.replace("postgres+asyncpg://", "postgres://")


async def _drop_schema() -> None:
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE')
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Module lifecycle
# ---------------------------------------------------------------------------
def setup_module(module):
    # Start clean, then enter the TestClient context so FastAPI's lifespan
    # connects the async database and provisions the schema + tables.
    asyncio.run(_drop_schema())
    client.__enter__()


def teardown_module(module):
    client.__exit__(None, None, None)
    asyncio.run(_drop_schema())


def _force_expire(access_token, days_ago=1):
    """Push a user's expiry into the past via a direct Postgres UPDATE against
    the isolated test schema."""
    past = db.now_utc() - timedelta(days=days_ago)

    async def _do():
        conn = await asyncpg.connect(_asyncpg_dsn())
        try:
            await conn.execute(f'SET search_path TO "{TEST_SCHEMA}", public')
            await conn.execute(
                "UPDATE users SET expires_at = $1 WHERE access_token = $2",
                past,
                access_token,
            )
        finally:
            await conn.close()

    asyncio.run(_do())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_create_user_returns_uuid_token_and_6_month_expiry():
    resp = client.post("/users", json={"email": "alice@example.com", "name": "Alice"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["plan_type"] == "individual"
    assert body["status"] == "active"
    assert len(body["id"]) == 36  # UUID string
    assert len(body["access_token"]) >= 40
    assert 175 <= body["days_remaining"] <= 190, body["days_remaining"]


def test_duplicate_email_rejected():
    client.post("/users", json={"email": "dupe@example.com", "name": "Dupe"})
    again = client.post("/users", json={"email": "dupe@example.com", "name": "Dupe2"})
    assert again.status_code == 409


def test_list_and_get_user():
    resp = client.post("/users", json={"email": "bob@example.com", "name": "Bob"})
    uid = resp.json()["id"]

    list_resp = client.get("/users")
    assert list_resp.status_code == 200
    assert any(u["id"] == uid for u in list_resp.json())

    one = client.get(f"/users/{uid}")
    assert one.status_code == 200
    assert one.json()["email"] == "bob@example.com"

    assert client.get("/users/00000000-0000-0000-0000-000000000000").status_code == 404


def test_validate_valid_token():
    resp = client.post("/users", json={"email": "carol@example.com", "name": "Carol"})
    token = resp.json()["access_token"]

    v = client.get(f"/validate/{token}")
    assert v.status_code == 200
    body = v.json()
    assert body["valid"] is True
    assert body["status"] == "active"
    assert body["days_remaining"] > 0
    assert body["plan_type"] == "individual"


def test_validate_expired_token():
    resp = client.post("/users", json={"email": "dave@example.com", "name": "Dave"})
    token = resp.json()["access_token"]
    _force_expire(token)

    v = client.get(f"/validate/{token}").json()
    assert v["valid"] is False
    assert v["status"] == "expired"
    assert v["days_remaining"] == 0


def test_validate_unknown_token():
    v = client.get("/validate/this-token-does-not-exist").json()
    assert v["valid"] is False
    assert v["status"] == "not_found"


def test_pause_then_validate_invalid_then_resume_valid():
    resp = client.post("/users", json={"email": "erin@example.com", "name": "Erin"})
    user = resp.json()
    uid, token = user["id"], user["access_token"]

    paused = client.post(f"/users/{uid}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert client.get(f"/validate/{token}").json()["valid"] is False

    resumed = client.post(f"/users/{uid}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"
    assert client.get(f"/validate/{token}").json()["valid"] is True


def test_cannot_resume_expired_user():
    resp = client.post("/users", json={"email": "frank@example.com", "name": "Frank"})
    user = resp.json()
    uid, token = user["id"], user["access_token"]

    client.post(f"/users/{uid}/pause")
    _force_expire(token)

    r = client.post(f"/users/{uid}/resume")
    assert r.status_code == 409


def test_revoke_is_permanent():
    resp = client.post("/users", json={"email": "grace@example.com", "name": "Grace"})
    user = resp.json()
    uid, token = user["id"], user["access_token"]

    revoked = client.post(f"/users/{uid}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert client.get(f"/validate/{token}").json()["valid"] is False

    assert client.post(f"/users/{uid}/resume").status_code == 409
    assert client.post(f"/users/{uid}/pause").status_code == 409


def test_enterprise_invite_inherits_parent_expiry():
    parent = client.post(
        "/users",
        json={"email": "corp@example.com", "name": "Corp Admin", "plan_type": "enterprise"},
    ).json()

    invite = client.post(
        f"/enterprise/{parent['id']}/invite",
        json={"email": "seat1@example.com", "name": "Seat One"},
    )
    assert invite.status_code == 201, invite.text
    child = invite.json()
    assert child["plan_type"] == "enterprise"
    assert child["parent_enterprise_id"] == parent["id"]
    assert child["expires_at"] == parent["expires_at"]


def test_enterprise_invite_rejected_for_individual_parent():
    parent = client.post(
        "/users", json={"email": "solo@example.com", "name": "Solo"}
    ).json()
    r = client.post(
        f"/enterprise/{parent['id']}/invite",
        json={"email": "x@example.com", "name": "X"},
    )
    assert r.status_code == 400


def test_enterprise_invite_rejected_when_parent_inactive():
    parent = client.post(
        "/users",
        json={"email": "corp2@example.com", "name": "Corp2", "plan_type": "enterprise"},
    ).json()
    client.post(f"/users/{parent['id']}/pause")
    r = client.post(
        f"/enterprise/{parent['id']}/invite",
        json={"email": "y@example.com", "name": "Y"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Direct runner (no pytest required)
# ---------------------------------------------------------------------------
def _run_all():
    setup_module(None)
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    try:
        for t in tests:
            try:
                t()
                print(f"  PASS  {t.__name__}")
            except Exception as e:  # noqa: BLE001
                failures += 1
                import traceback

                print(f"  FAIL  {t.__name__}: {e}")
                traceback.print_exc()
    finally:
        teardown_module(None)

    print(f"\n{len(tests) - failures}/{len(tests)} passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
