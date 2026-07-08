"""
backend/schemas.py
Pydantic request/response models for the SaaS API. IDs are UUID strings
(Supabase/Postgres uuid), timestamps are tz-aware datetimes.

Strict validation enforces least-privilege input boundaries — oversized or
malformed payloads are rejected before reaching the database layer.
"""

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# --- Field length caps (mitigate buffer-style abuse and log bloat) ---
MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 254  # RFC 5321
MAX_URL_LENGTH = 2048
MAX_TOKEN_LENGTH = 128
MAX_PLAN_TYPE_LENGTH = 32

VALID_PLAN_TYPES = ("individual", "enterprise")

# HTTPS-only checkout redirects in production; localhost allowed for dev.
_CHECKOUT_URL_RE = re.compile(
    r"^https://[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$",
    re.IGNORECASE,
)
_LOCAL_CHECKOUT_URL_RE = re.compile(
    r"^http://(localhost|127\.0\.0\.1)(:\d+)?/[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%-]*$",
    re.IGNORECASE,
)


def _validate_checkout_url(url: str) -> str:
    """Reject javascript: / data: / open-redirect payloads in Stripe callbacks."""
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"URL must be at most {MAX_URL_LENGTH} characters")
    if _CHECKOUT_URL_RE.match(url) or _LOCAL_CHECKOUT_URL_RE.match(url):
        return url
    raise ValueError("success_url and cancel_url must be HTTPS (or http://localhost for dev)")


class UserCreate(BaseModel):
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    plan_type: Literal["individual", "enterprise"] = "individual"

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class EnterpriseInvite(BaseModel):
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class CheckoutRequest(BaseModel):
    success_url: str = Field(max_length=MAX_URL_LENGTH)
    cancel_url: str = Field(max_length=MAX_URL_LENGTH)
    email: Optional[EmailStr] = Field(default=None, max_length=MAX_EMAIL_LENGTH)

    @field_validator("success_url", "cancel_url")
    @classmethod
    def validate_redirect_urls(cls, v: str) -> str:
        return _validate_checkout_url(v)


class CheckoutResponse(BaseModel):
    checkout_url: str = Field(max_length=MAX_URL_LENGTH)


class UserOut(BaseModel):
    id: str = Field(max_length=36)
    email: str = Field(max_length=MAX_EMAIL_LENGTH)
    name: Optional[str] = Field(default=None, max_length=MAX_NAME_LENGTH)
    plan_type: str = Field(max_length=MAX_PLAN_TYPE_LENGTH)
    access_token: str = Field(max_length=MAX_TOKEN_LENGTH)
    stripe_customer_id: Optional[str] = Field(default=None, max_length=255)
    parent_enterprise_id: Optional[str] = Field(default=None, max_length=36)
    created_at: datetime
    expires_at: datetime
    status: str = Field(max_length=32)
    days_remaining: int = Field(ge=0)


class ValidateResponse(BaseModel):
    valid: bool
    days_remaining: int = Field(ge=0)
    plan_type: str = Field(max_length=MAX_PLAN_TYPE_LENGTH)
    status: str = Field(max_length=32)


class AdminVerifyResponse(BaseModel):
    ok: bool = True


class AdminStats(BaseModel):
    total_users: int = Field(ge=0)
    total_active: int = Field(ge=0)
    pending_renewals: int = Field(ge=0)
    paused: int = Field(ge=0)
    revoked: int = Field(ge=0)
    active_individual: int = Field(ge=0)
    active_enterprise: int = Field(ge=0)
