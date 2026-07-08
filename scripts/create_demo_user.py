"""
Provision the investor demo user in Supabase Postgres.

Loads DATABASE_URL and DEMO_ACCESS_TOKEN from .env.local (repo root).
If DEMO_ACCESS_TOKEN is unset, generates one and prints it for you to save.

Usage:
    python scripts/create_demo_user.py
    python scripts/create_demo_user.py --email demo@sportsanalyzer.app
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta

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


async def _ensure_demo_user(
    email: str,
    name: str,
    plan_type: str,
    access_token: str,
) -> dict:
    from backend import db

    if db.database is None:
        print(
            "ERROR: DATABASE_URL is missing or is still a placeholder in .env.local",
            file=sys.stderr,
        )
        raise SystemExit(2)

    await db.database.connect()
    try:
        await db.ensure_schema()
        expires_at = datetime.now(timezone.utc) + relativedelta(years=2)
        existing = await db.get_user_by_email(email)
        if existing:
            await db.database.execute(
                """
                UPDATE users
                SET access_token = :token,
                    plan_type = :plan,
                    status = :status,
                    expires_at = :expires,
                    name = :name
                WHERE email = :email
                """,
                {
                    "token": access_token,
                    "plan": plan_type,
                    "status": db.STATUS_ACTIVE,
                    "expires": expires_at,
                    "name": name,
                    "email": email,
                },
            )
            row = await db.get_user_by_email(email)
            print(f"[create_demo] Updated existing demo user: {email}")
        else:
            row = await db.create_user(
                email=email,
                name=name,
                plan_type=plan_type,
                expires_at=expires_at,
                status=db.STATUS_ACTIVE,
                access_token=access_token,
            )
            print(f"[create_demo] Created demo user: {email} ({plan_type})")
    finally:
        await db.database.disconnect()

    return row


async def _run(email: str, name: str, plan_type: str) -> int:
    _load_env_local()
    token = os.environ.get("DEMO_ACCESS_TOKEN", "").strip()
    if not token:
        token = secrets.token_urlsafe(32)
        print(
            "[create_demo] DEMO_ACCESS_TOKEN not set — generated a new token.\n"
            "Add these lines to .env.local and web/.env.production:\n"
            f"  DEMO_ACCESS_TOKEN={token}\n"
            f"  NEXT_PUBLIC_DEMO_ACCESS_TOKEN={token}\n"
        )

    row = await _ensure_demo_user(email, name, plan_type, token)
    dashboard_url = f"{DASHBOARD_BASE}/?token={token}"
    print("\n================ INVESTOR DEMO ACCESS ================")
    print(f"  Email:          {row['email']}")
    print(f"  Name:           {row.get('name') or name}")
    print(f"  Plan:           {row['plan_type']}")
    print(f"  Status:         {row['status']}")
    print(f"  Expires:        {row['expires_at']}")
    print(f"  Access token:   {token}")
    print(f"  Dashboard URL:  {dashboard_url}")
    print("======================================================")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or refresh investor demo user")
    parser.add_argument("--email", default="demo@sportsanalyzer.app")
    parser.add_argument("--name", default="Investor Demo")
    parser.add_argument("--plan", default="enterprise", dest="plan_type")
    args = parser.parse_args()
    return asyncio.run(_run(args.email, args.name, args.plan_type))


if __name__ == "__main__":
    raise SystemExit(main())
