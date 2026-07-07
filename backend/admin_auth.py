"""
backend/admin_auth.py
Shared admin API-key verification for protected management routes.

Set ADMIN_API_KEY in the environment (Render dashboard, sync:false). Clients
send it as the X-Admin-Key request header.
"""

import os
import secrets

from fastapi import Header, HTTPException

ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "").strip()


def require_admin_key(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
) -> None:
    """FastAPI dependency — rejects requests without a valid admin key."""
    if not ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_API_KEY is not configured on the server",
        )
    if not x_admin_key or not secrets.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")
