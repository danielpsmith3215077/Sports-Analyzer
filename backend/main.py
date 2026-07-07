"""
backend/main.py
Cloud-ready FastAPI service for the Sports Analyzer platform (Milestone 1).

Async, Supabase/PostgreSQL-backed (via the `databases` library) account +
licensing core, plus the carried-over Stripe checkout/webhook endpoints ported
to the async data layer.

Run locally:
    uvicorn backend.main:app --reload --port 8000

Set DATABASE_URL to your Supabase Postgres connection string in production;
it defaults to a local async SQLite database for zero-config development.
"""

import logging
from contextlib import asynccontextmanager

import stripe
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend import db, stripe_config
from backend.admin_auth import require_admin_key
from backend.schemas import (
    AdminStats,
    AdminVerifyResponse,
    CheckoutRequest,
    CheckoutResponse,
    EnterpriseInvite,
    UserCreate,
    UserOut,
    ValidateResponse,
)


logger = logging.getLogger("sports_analyzer.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to Supabase Postgres, but do NOT crash the whole service if the
    # database is briefly unreachable — the /api/healthcheck keep-alive must
    # keep responding so Render's free tier does not spin the container down.
    try:
        await db.connect()
    except Exception as exc:  # noqa: BLE001
        logger.error("Startup DB connect failed (API will still serve health): %s", exc)
    try:
        yield
    finally:
        try:
            await db.disconnect()
        except Exception:  # noqa: BLE001
            pass


app = FastAPI(
    title="Sports Analyzer — Cloud Core API",
    description="Supabase-backed accounts, licensing, and Stripe payments.",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS: allow the Streamlit clients (8501/8502/8503) and Vercel edge networks.
# ---------------------------------------------------------------------------
_LOCAL_ORIGINS = [
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1")
    for port in (8501, 8502, 8503)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_LOCAL_ORIGINS,
    allow_origin_regex=r"https://.*\.(vercel\.app|onrender\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def serialize_user(row: dict) -> UserOut:
    parent = row.get("parent_enterprise_id")
    return UserOut(
        id=str(row["id"]),
        email=row["email"],
        name=row.get("name"),
        plan_type=row["plan_type"],
        access_token=row["access_token"],
        stripe_customer_id=row.get("stripe_customer_id"),
        parent_enterprise_id=str(parent) if parent is not None else None,
        created_at=db.parse_dt(row["created_at"]),
        expires_at=db.parse_dt(row["expires_at"]),
        status=row["status"],
        days_remaining=db.days_remaining(row["expires_at"]),
    )


async def _get_user_or_404(user_id: str) -> dict:
    row = await db.get_user(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return row


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"service": "Sports Analyzer — Cloud Core API", "status": "ok"}


@app.get("/api/healthcheck")
async def healthcheck():
    """Lightweight keep-alive endpoint (zero database overhead). Pinged by
    cron-job.org to keep the Render free-tier container from sleeping."""
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Admin auth + summary (X-Admin-Key header)
# ---------------------------------------------------------------------------
_RENEWAL_WINDOW_DAYS = 7


def _compute_admin_stats(rows: list[dict]) -> AdminStats:
    active = [r for r in rows if r.get("status") == db.STATUS_ACTIVE]
    paused = [r for r in rows if r.get("status") == db.STATUS_PAUSED]
    revoked = [r for r in rows if r.get("status") == db.STATUS_REVOKED]
    pending = [
        r
        for r in active
        if 0 <= db.days_remaining(r["expires_at"]) <= _RENEWAL_WINDOW_DAYS
    ]
    active_individual = sum(1 for r in active if r.get("plan_type") == db.PLAN_INDIVIDUAL)
    active_enterprise = sum(1 for r in active if r.get("plan_type") == db.PLAN_ENTERPRISE)
    return AdminStats(
        total_users=len(rows),
        total_active=len(active),
        pending_renewals=len(pending),
        paused=len(paused),
        revoked=len(revoked),
        active_individual=active_individual,
        active_enterprise=active_enterprise,
    )


@app.post("/admin/verify", response_model=AdminVerifyResponse)
async def admin_verify(_: None = Depends(require_admin_key)):
    """Lightweight login check for admin UIs (no side effects)."""
    return AdminVerifyResponse()


@app.get("/admin/stats", response_model=AdminStats)
async def admin_stats(_: None = Depends(require_admin_key)):
    rows = await db.list_users()
    return _compute_admin_stats(rows)


# ---------------------------------------------------------------------------
# Milestone 1: user + license endpoints (admin-protected)
# ---------------------------------------------------------------------------
@app.post("/users", response_model=UserOut, status_code=201)
async def create_user(payload: UserCreate, _: None = Depends(require_admin_key)):
    if payload.plan_type not in db.VALID_PLANS:
        raise HTTPException(status_code=422, detail=f"Invalid plan_type: {payload.plan_type}")
    existing = await db.get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    row = await db.create_user(
        email=payload.email, name=payload.name, plan_type=payload.plan_type
    )
    return serialize_user(row)


@app.get("/users", response_model=list[UserOut])
async def list_users(_: None = Depends(require_admin_key)):
    rows = await db.list_users()
    return [serialize_user(r) for r in rows]


@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: str, _: None = Depends(require_admin_key)):
    return serialize_user(await _get_user_or_404(user_id))


@app.post("/users/{user_id}/pause", response_model=UserOut)
async def pause_user(user_id: str, _: None = Depends(require_admin_key)):
    row = await _get_user_or_404(user_id)
    if row["status"] == db.STATUS_REVOKED:
        raise HTTPException(status_code=409, detail="Cannot pause a revoked account")
    updated = await db.update_status(user_id, db.STATUS_PAUSED)
    return serialize_user(updated)


@app.post("/users/{user_id}/resume", response_model=UserOut)
async def resume_user(user_id: str, _: None = Depends(require_admin_key)):
    row = await _get_user_or_404(user_id)
    if row["status"] == db.STATUS_REVOKED:
        raise HTTPException(status_code=409, detail="Cannot resume a revoked account")
    if db.parse_dt(row["expires_at"]) <= db.now_utc():
        raise HTTPException(status_code=409, detail="Cannot resume an expired account")
    updated = await db.update_status(user_id, db.STATUS_ACTIVE)
    return serialize_user(updated)


@app.post("/users/{user_id}/revoke", response_model=UserOut)
async def revoke_user(user_id: str, _: None = Depends(require_admin_key)):
    await _get_user_or_404(user_id)
    updated = await db.update_status(user_id, db.STATUS_REVOKED)
    return serialize_user(updated)


@app.get("/validate/{access_token}", response_model=ValidateResponse)
async def validate_token(access_token: str):
    row = await db.get_user_by_token(access_token)
    if row is None:
        return ValidateResponse(
            valid=False, days_remaining=0, plan_type="", status="not_found"
        )

    # Auto-flip a lapsed-but-still-"active" record to expired so status is honest.
    if row["status"] == db.STATUS_ACTIVE and db.parse_dt(row["expires_at"]) <= db.now_utc():
        row = await db.update_status(row["id"], db.STATUS_EXPIRED)

    return ValidateResponse(
        valid=db.is_valid_row(row),
        days_remaining=db.days_remaining(row["expires_at"]),
        plan_type=row["plan_type"],
        status=row["status"],
    )


@app.post("/enterprise/{enterprise_user_id}/invite", response_model=UserOut, status_code=201)
async def enterprise_invite(
    enterprise_user_id: str,
    payload: EnterpriseInvite,
    _: None = Depends(require_admin_key),
):
    parent = await _get_user_or_404(enterprise_user_id)
    if parent["plan_type"] != db.PLAN_ENTERPRISE:
        raise HTTPException(
            status_code=400, detail="Parent account is not on an enterprise plan"
        )
    if not db.is_valid_row(parent):
        raise HTTPException(
            status_code=400, detail="Parent enterprise account is not active"
        )
    if await db.get_user_by_email(payload.email):
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    invited = await db.create_user(
        email=payload.email,
        name=payload.name,
        plan_type=db.PLAN_ENTERPRISE,
        # Mirror the parent's exact expiration matrix (not a fresh 6 months).
        expires_at=db.parse_dt(parent["expires_at"]),
        parent_enterprise_id=str(parent["id"]),
    )
    return serialize_user(invited)


# ---------------------------------------------------------------------------
# Stripe checkout + webhooks (async, DB-backed)
#
# Apple App Store Guideline 3.1.3(b) — Multiplatform Services:
# Monetization is WEB-ONLY. These endpoints hand back a Stripe-hosted checkout
# URL (subscription mode); pricing, checkout, and credit-card management occur
# exclusively on the web. Licenses are activated globally server-side, so the
# mobile/desktop wrapper only reads the resulting entitlement (via /validate)
# and never presents in-app purchase UI — keeping the wrapper fee-free.
# ---------------------------------------------------------------------------
def _create_checkout_session(plan_type: str, payload: CheckoutRequest) -> CheckoutResponse:
    if not stripe_config.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured on the server (missing secret key or price IDs).",
        )
    price_id = stripe_config.price_id_for_plan(plan_type)
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            customer_email=payload.email,
            metadata={"plan_type": plan_type},
            subscription_data={"metadata": {"plan_type": plan_type}},
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Stripe checkout failed: {e}")

    url = session.get("url") if isinstance(session, dict) else getattr(session, "url", None)
    if not url:
        raise HTTPException(status_code=502, detail="Stripe did not return a checkout URL")
    return CheckoutResponse(checkout_url=url)


@app.post("/checkout/individual", response_model=CheckoutResponse)
async def checkout_individual(payload: CheckoutRequest):
    return _create_checkout_session(db.PLAN_INDIVIDUAL, payload)


@app.post("/checkout/enterprise", response_model=CheckoutResponse)
async def checkout_enterprise(payload: CheckoutRequest):
    return _create_checkout_session(db.PLAN_ENTERPRISE, payload)


def _extract_plan_type(session_obj: dict) -> str:
    metadata = session_obj.get("metadata") or {}
    if metadata.get("plan_type") in db.VALID_PLANS:
        return metadata["plan_type"]
    line_items = session_obj.get("line_items") or {}
    for item in line_items.get("data", []):
        price = item.get("price") or {}
        pid = price.get("id")
        if pid:
            return stripe_config.plan_for_price_id(pid)
    return db.PLAN_INDIVIDUAL


async def handle_stripe_event(event: dict) -> dict:
    """Async, testable webhook dispatcher."""
    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        plan_type = _extract_plan_type(obj)
        customer_id = obj.get("customer")
        details = obj.get("customer_details") or {}
        email = details.get("email") or obj.get("customer_email") or "unknown@unknown"
        name = details.get("name") or (obj.get("metadata") or {}).get("name") or email.split("@")[0]

        existing = (
            await db.get_user_by_stripe_customer(customer_id) if customer_id else None
        )
        if existing:
            user = await db.update_status(existing["id"], db.STATUS_ACTIVE)
        else:
            user = await db.create_user(
                email=email, name=name, plan_type=plan_type,
                stripe_customer_id=customer_id,
            )
        print(
            f"[stripe] checkout.session.completed -> user {user['id']} ({user['email']}), "
            f"plan={user['plan_type']}. Access link: "
            f"http://localhost:8501/?token={user['access_token']}"
        )
        return {"action": "created", "user_id": user["id"], "plan_type": user["plan_type"]}

    if event_type == "invoice.payment_failed":
        customer_id = obj.get("customer")
        user = await db.get_user_by_stripe_customer(customer_id) if customer_id else None
        if user and user["status"] != db.STATUS_REVOKED:
            await db.update_status(user["id"], db.STATUS_PAUSED)
            print(f"[stripe] invoice.payment_failed -> user {user['id']} paused.")
            return {"action": "paused", "user_id": user["id"]}
        return {"action": "noop", "reason": "no matching active user"}

    if event_type == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        user = await db.get_user_by_stripe_customer(customer_id) if customer_id else None
        if user and user["status"] != db.STATUS_REVOKED:
            await db.update_status(user["id"], db.STATUS_EXPIRED)
            print(f"[stripe] customer.subscription.deleted -> user {user['id']} expired.")
            return {"action": "expired", "user_id": user["id"]}
        return {"action": "noop", "reason": "no matching user"}

    return {"action": "ignored", "type": event_type}


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not stripe_config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    result = await handle_stripe_event(dict(event))
    return {"received": True, "result": result}
