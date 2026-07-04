"""
backend/schemas.py
Pydantic request/response models for the SaaS API. IDs are UUID strings
(Supabase/Postgres uuid), timestamps are tz-aware datetimes.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)
    plan_type: str = Field(default="individual")


class EnterpriseInvite(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)


class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str
    email: Optional[EmailStr] = None


class CheckoutResponse(BaseModel):
    checkout_url: str


class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    plan_type: str
    access_token: str
    stripe_customer_id: Optional[str] = None
    parent_enterprise_id: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    status: str
    days_remaining: int


class ValidateResponse(BaseModel):
    valid: bool
    days_remaining: int
    plan_type: str
    status: str
