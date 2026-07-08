"""
Provision an owner/enterprise user directly against Supabase Postgres.

Loads DATABASE_URL from .env.local (repo root). Prints access_token and
dashboard URL only — never secrets from the environment.

Usage:
    python scripts/create_owner_user.py
    python scripts/create_owner_user.py --email user@example.com --name Owner --plan enterprise
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

DASHBOARD_BASE = os.environ.get(
    "DASHBOARD_URL",
    "https://sportsanalyzer-dashboard.onrender.com",
).rstrip("/")


def _load_env_local() -> None:
    path = os.path.join(_ROOT, ".env.local")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


async def _run(email: str, name: str, plan_type: str) -> int:
    _load_env_local()
    from backend import db

    if db.database is None:
        print(
            "ERROR: DATABASE_URL is missing or is still a placeholder in .env.local",
            file=sys.stderr,
        )
        return 2

    await db.database.connect()
    try:
        await db.ensure_schema()
        existing = await db.get_user_by_email(email)
        if existing:
            row = existing
            print(f"[create_owner] User already exists: {email}")
        else:
            row = await db.create_user(email=email, name=name, plan_type=plan_type)
            print(f"[create_owner] Created user: {email} ({plan_type})")
    finally:
        await db.database.disconnect()

    token = row["access_token"]
    dashboard_url = f"{DASHBOARD_BASE}/?token={token}"
    print("\n================ OWNER ACCESS ================")
    print(f"  Email:          {row['email']}")
    print(f"  Name:           {row.get('name') or name}")
    print(f"  Plan:           {row['plan_type']}")
    print(f"  Status:         {row['status']}")
    print(f"  User ID:        {row['id']}")
    print(f"  Access token:   {token}")
    print(f"  Dashboard URL:  {dashboard_url}")
    print("==============================================")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or fetch owner user access")
    parser.add_argument("--email", default="dps316@icloud.com")
    parser.add_argument("--name", default="Owner")
    parser.add_argument("--plan", default="enterprise", dest="plan_type")
    args = parser.parse_args()
    return asyncio.run(_run(args.email, args.name, args.plan_type))


if __name__ == "__main__":
    raise SystemExit(main())
