"""
backend/init_db.py
Schema migration runner for the remote Supabase Postgres cluster.

Loads DATABASE_URL from the environment (or a local .env.local), connects to
Supabase, idempotently creates every required table (user profiles, Stripe
payment webhooks, match telemetry analytics logs), then verifies each table is
present and prints a success checklist.

Run:
    python -m backend.init_db
    # or
    python backend/init_db.py
"""

import asyncio
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _load_env_local() -> None:
    """Minimal .env.local loader (no python-dotenv dependency required)."""
    path = os.path.join(_ROOT, ".env.local")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Do not clobber values already exported into the environment.
            os.environ.setdefault(key, value)


async def _run() -> int:
    _load_env_local()
    # Import after env is loaded so db.py resolves DATABASE_URL correctly.
    from backend import db

    if db.database is None:
        print(
            "ERROR: DATABASE_URL is missing or is still a placeholder.\n"
            "       Set it to your real Supabase connection string, e.g.:\n"
            '       DATABASE_URL="postgresql://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres"',
            file=sys.stderr,
        )
        return 2

    print(f"[init_db] Connecting to Supabase Postgres ...")
    await db.database.connect()
    try:
        print("[init_db] Applying schema (idempotent CREATE TABLE / INDEX) ...")
        await db.ensure_schema()

        print("[init_db] Verifying tables via information_schema ...")
        present = await db.verify_schema()
    finally:
        await db.database.disconnect()

    print("\n================ MIGRATION CHECKLIST ================")
    all_ok = True
    for table, exists in present.items():
        mark = "OK  " if exists else "FAIL"
        all_ok = all_ok and exists
        print(f"  [{mark}] public.{table}")
    print("=====================================================")
    if all_ok:
        print("SUCCESS: All Supabase tables written and verified.")
        return 0
    print("FAILURE: One or more tables were not created.", file=sys.stderr)
    return 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
