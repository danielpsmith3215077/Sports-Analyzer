"""
test_saas_integration.py
Stage 6 end-to-end integration test. Unlike backend/test_backend.py (which uses
an in-process TestClient), this actually STARTS the FastAPI backend with uvicorn
in a subprocess and drives it over real HTTP:

  1. create a user via POST /users
  2. validate their token (valid=True)
  3. pause -> /validate returns valid=False
  4. resume -> /validate returns valid=True again
  5. create an enterprise invite -> confirm it inherits the parent's expiration

The local SQLite fallback has been removed, so this requires a real Postgres
database via TEST_DATABASE_URL. When unset, the module is SKIPPED (never
failed). Every run is isolated inside a throwaway schema (DB_SCHEMA) that is
dropped afterwards, so production `public` tables are never touched.

Run directly (exits 0 on success):
    TEST_DATABASE_URL="postgresql://user:pass@host:5432/dbname" python3 test_saas_integration.py
or with pytest:
    TEST_DATABASE_URL="postgresql://user:pass@host:5432/dbname" pytest test_saas_integration.py
"""

import asyncio
import os
import socket
import subprocess
import sys
import time

import pytest
import requests

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
            f"({_LIVE_SUPABASE_PROJECT_REF}). This suite starts a live backend "
            f"process against the configured database and must only ever run "
            f"against an isolated, disposable test database. Point "
            f"TEST_DATABASE_URL at a separate Postgres instance/project.",
            returncode=1,
        )

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()

if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set — skipping Postgres-backed integration test. "
        "Set it to an isolated Postgres/Supabase database to run it.",
        allow_module_level=True,
    )

TEST_SCHEMA = "sa_test_integration"
ADMIN_API_KEY = "test-admin-key"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_API_KEY}


def _asyncpg_dsn() -> str:
    dsn = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    return dsn.replace("postgres+asyncpg://", "postgres://")


def _drop_schema() -> None:
    import asyncpg

    async def _do():
        conn = await asyncpg.connect(_asyncpg_dsn())
        try:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE')
        finally:
            await conn.close()

    asyncio.run(_do())


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_server(base_url, proc, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Backend process exited early with code {proc.returncode}"
            )
        try:
            r = requests.get(f"{base_url}/", timeout=2)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.4)
    raise RuntimeError(f"Backend did not become ready within {timeout}s at {base_url}")


def run_integration():
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    # Isolated Postgres schema for this run; start clean.
    _drop_schema()

    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DATABASE_URL
    env["DB_SCHEMA"] = TEST_SCHEMA
    env["ADMIN_API_KEY"] = ADMIN_API_KEY
    env["RATE_LIMIT_ENABLED"] = "false"

    repo_root = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    failures = []

    def check(cond, msg):
        if cond:
            print(f"  PASS  {msg}")
        else:
            failures.append(msg)
            print(f"  FAIL  {msg}")

    try:
        _wait_for_server(base_url, proc)
        print(f"Backend up at {base_url}")

        # 1. create individual user
        r = requests.post(
            f"{base_url}/users",
            json={"email": "integration@example.com", "name": "Integration User"},
            headers=ADMIN_HEADERS,
            timeout=10,
        )
        check(r.status_code == 201, "POST /users creates a user (201)")
        user = r.json()
        token = user["access_token"]

        # 2. validate token -> valid
        v = requests.get(f"{base_url}/validate/{token}", timeout=10).json()
        check(v["valid"] is True, "token validates as valid immediately after creation")
        check(v["days_remaining"] > 150, "new user has ~6-month license")

        # 3. pause -> invalid
        rp = requests.post(f"{base_url}/users/{user['id']}/pause", headers=ADMIN_HEADERS, timeout=10)
        check(rp.status_code == 200, "POST /users/{id}/pause succeeds")
        v = requests.get(f"{base_url}/validate/{token}", timeout=10).json()
        check(v["valid"] is False, "paused user now validates as INVALID")

        # 4. resume -> valid again
        rr = requests.post(f"{base_url}/users/{user['id']}/resume", headers=ADMIN_HEADERS, timeout=10)
        check(rr.status_code == 200, "POST /users/{id}/resume succeeds")
        v = requests.get(f"{base_url}/validate/{token}", timeout=10).json()
        check(v["valid"] is True, "resumed user validates as VALID again")

        # 5. enterprise invite inherits parent expiration
        parent = requests.post(
            f"{base_url}/users",
            json={"email": "ent@example.com", "name": "Ent Admin", "plan_type": "enterprise"},
            headers=ADMIN_HEADERS,
            timeout=10,
        ).json()
        invite = requests.post(
            f"{base_url}/enterprise/{parent['id']}/invite",
            json={"email": "seat@example.com", "name": "Seat"},
            headers=ADMIN_HEADERS,
            timeout=10,
        )
        check(invite.status_code == 201, "POST /enterprise/{id}/invite succeeds")
        child = invite.json()
        check(
            child["expires_at"] == parent["expires_at"],
            "enterprise invite inherits parent's exact expiration date",
        )
        check(
            child["parent_enterprise_id"] == parent["id"],
            "enterprise invite is linked to the parent account",
        )

        # revoke is permanent
        requests.post(f"{base_url}/users/{user['id']}/revoke", headers=ADMIN_HEADERS, timeout=10)
        v = requests.get(f"{base_url}/validate/{token}", timeout=10).json()
        check(v["valid"] is False and v["status"] == "revoked",
              "revoked user is permanently invalid")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        _drop_schema()

    total = 10
    print(f"\n{total - len(failures)}/{total} checks passed.")
    return 1 if failures else 0


def test_saas_end_to_end():
    """pytest entry point."""
    assert run_integration() == 0


if __name__ == "__main__":
    sys.exit(run_integration())
