"""
backend/test_stripe_integration.py
Stripe integration tests, ported to the async Supabase/Postgres-ready layer.
Never hits the real Stripe API:
  * webhook events are hand-built dicts passed to the async handle_stripe_event()
  * checkout session creation is exercised with stripe.checkout.Session.create
    monkeypatched to return a fake session.

Runs against a local async SQLite database (databases + aiosqlite).

Run:
    pytest backend/test_stripe_integration.py
    # or directly:
    python3 -m backend.test_stripe_integration
"""

import asyncio
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./backend/_pytest_saas.db")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")

from fastapi.testclient import TestClient  # noqa: E402

from backend import db, main, stripe_config  # noqa: E402
from backend.main import app  # noqa: E402

DB_FILE = os.path.join("backend", "_pytest_saas.db")


def setup_module(module):
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except OSError:
            pass


def run_async(async_fn):
    """Connect the async DB, run the coroutine, then disconnect."""
    async def _wrap():
        await db.connect()
        try:
            return await async_fn()
        finally:
            await db.disconnect()

    return asyncio.run(_wrap())


def _completed_event(customer_id, email, plan_type):
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": customer_id,
                "customer_details": {"email": email, "name": "Test Buyer"},
                "metadata": {"plan_type": plan_type},
            }
        },
    }


# ---------------------------------------------------------------------------
# Webhook handler tests
# ---------------------------------------------------------------------------
def test_checkout_completed_creates_individual_user():
    async def body():
        res = await main.handle_stripe_event(
            _completed_event("cus_indiv", "buyer1@example.com", "individual")
        )
        assert res["action"] == "created"
        user = await db.get_user_by_stripe_customer("cus_indiv")
        assert user is not None
        assert user["plan_type"] == "individual"
        assert user["status"] == "active"
        assert db.days_remaining(user["expires_at"]) > 150

    run_async(body)


def test_checkout_completed_creates_enterprise_user():
    async def body():
        res = await main.handle_stripe_event(
            _completed_event("cus_ent", "buyer2@example.com", "enterprise")
        )
        assert res["action"] == "created"
        user = await db.get_user_by_stripe_customer("cus_ent")
        assert user["plan_type"] == "enterprise"

    run_async(body)


def test_plan_type_derived_from_price_id_when_no_metadata():
    original = stripe_config.STRIPE_ENTERPRISE_PRICE_ID
    stripe_config.STRIPE_ENTERPRISE_PRICE_ID = "price_ent_123"
    try:
        async def body():
            event = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": "cus_price_derived",
                        "customer_details": {"email": "buyer3@example.com"},
                        "metadata": {},
                        "line_items": {"data": [{"price": {"id": "price_ent_123"}}]},
                    }
                },
            }
            await main.handle_stripe_event(event)
            user = await db.get_user_by_stripe_customer("cus_price_derived")
            assert user["plan_type"] == "enterprise"

        run_async(body)
    finally:
        stripe_config.STRIPE_ENTERPRISE_PRICE_ID = original


def test_payment_failed_pauses_user():
    async def body():
        await main.handle_stripe_event(
            _completed_event("cus_fail", "buyer4@example.com", "individual")
        )
        res = await main.handle_stripe_event(
            {"type": "invoice.payment_failed", "data": {"object": {"customer": "cus_fail"}}}
        )
        assert res["action"] == "paused"
        user = await db.get_user_by_stripe_customer("cus_fail")
        assert user["status"] == "paused"

    run_async(body)


def test_subscription_deleted_expires_user():
    async def body():
        await main.handle_stripe_event(
            _completed_event("cus_del", "buyer5@example.com", "individual")
        )
        res = await main.handle_stripe_event(
            {"type": "customer.subscription.deleted", "data": {"object": {"customer": "cus_del"}}}
        )
        assert res["action"] == "expired"
        user = await db.get_user_by_stripe_customer("cus_del")
        assert user["status"] == "expired"

    run_async(body)


def test_payment_failed_for_unknown_customer_is_noop():
    async def body():
        res = await main.handle_stripe_event(
            {"type": "invoice.payment_failed", "data": {"object": {"customer": "cus_ghost"}}}
        )
        assert res["action"] == "noop"

    run_async(body)


def test_duplicate_checkout_does_not_create_second_user():
    async def body():
        await main.handle_stripe_event(
            _completed_event("cus_dup", "dup@example.com", "individual")
        )
        await main.handle_stripe_event(
            _completed_event("cus_dup", "dup@example.com", "individual")
        )
        users = await db.list_users()
        matching = [u for u in users if u["stripe_customer_id"] == "cus_dup"]
        assert len(matching) == 1

    run_async(body)


def test_unhandled_event_is_ignored():
    async def body():
        res = await main.handle_stripe_event({"type": "ping", "data": {"object": {}}})
        assert res["action"] == "ignored"

    run_async(body)


# ---------------------------------------------------------------------------
# Checkout session creation (Stripe API fully mocked; no DB needed)
# ---------------------------------------------------------------------------
def test_create_checkout_session_mocked():
    import stripe

    from backend.schemas import CheckoutRequest

    originals = (
        stripe_config.STRIPE_SECRET_KEY,
        stripe_config.STRIPE_INDIVIDUAL_PRICE_ID,
        stripe_config.STRIPE_ENTERPRISE_PRICE_ID,
    )
    stripe_config.STRIPE_SECRET_KEY = "sk_test_dummy"
    stripe_config.STRIPE_INDIVIDUAL_PRICE_ID = "price_ind"
    stripe_config.STRIPE_ENTERPRISE_PRICE_ID = "price_ent"

    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return {"url": "https://checkout.stripe.com/c/pay/test_session_123"}

    original_create = stripe.checkout.Session.create
    stripe.checkout.Session.create = staticmethod(fake_create)
    try:
        resp = main._create_checkout_session(
            "individual",
            CheckoutRequest(
                success_url="https://app/success",
                cancel_url="https://app/cancel",
                email="checkout@example.com",
            ),
        )
        assert resp.checkout_url.startswith("https://checkout.stripe.com/")
        assert captured["mode"] == "subscription"
        assert captured["line_items"][0]["price"] == "price_ind"
        assert captured["success_url"] == "https://app/success"
    finally:
        stripe.checkout.Session.create = original_create
        (
            stripe_config.STRIPE_SECRET_KEY,
            stripe_config.STRIPE_INDIVIDUAL_PRICE_ID,
            stripe_config.STRIPE_ENTERPRISE_PRICE_ID,
        ) = originals


def test_checkout_disabled_when_unconfigured():
    from fastapi import HTTPException

    from backend.schemas import CheckoutRequest

    originals = (
        stripe_config.STRIPE_SECRET_KEY,
        stripe_config.STRIPE_INDIVIDUAL_PRICE_ID,
        stripe_config.STRIPE_ENTERPRISE_PRICE_ID,
    )
    stripe_config.STRIPE_SECRET_KEY = ""
    stripe_config.STRIPE_INDIVIDUAL_PRICE_ID = ""
    stripe_config.STRIPE_ENTERPRISE_PRICE_ID = ""
    try:
        raised = False
        try:
            main._create_checkout_session(
                "individual",
                CheckoutRequest(success_url="https://a", cancel_url="https://b"),
            )
        except HTTPException as e:
            raised = True
            assert e.status_code == 503
        assert raised, "Expected HTTPException when Stripe unconfigured"
    finally:
        (
            stripe_config.STRIPE_SECRET_KEY,
            stripe_config.STRIPE_INDIVIDUAL_PRICE_ID,
            stripe_config.STRIPE_ENTERPRISE_PRICE_ID,
        ) = originals


# ---------------------------------------------------------------------------
# HTTP-level tests: fire payloads directly into the live FastAPI routers.
# TestClient's context manager runs the lifespan (connects the async DB).
# ---------------------------------------------------------------------------
def _configure_stripe():
    """Return a restore() closure; sets test-mode config on stripe_config."""
    originals = (
        stripe_config.STRIPE_SECRET_KEY,
        stripe_config.STRIPE_INDIVIDUAL_PRICE_ID,
        stripe_config.STRIPE_ENTERPRISE_PRICE_ID,
        stripe_config.STRIPE_WEBHOOK_SECRET,
    )
    stripe_config.STRIPE_SECRET_KEY = "sk_test_dummy"
    stripe_config.STRIPE_INDIVIDUAL_PRICE_ID = "price_ind"
    stripe_config.STRIPE_ENTERPRISE_PRICE_ID = "price_ent"
    stripe_config.STRIPE_WEBHOOK_SECRET = "whsec_test_dummy"

    def restore():
        (
            stripe_config.STRIPE_SECRET_KEY,
            stripe_config.STRIPE_INDIVIDUAL_PRICE_ID,
            stripe_config.STRIPE_ENTERPRISE_PRICE_ID,
            stripe_config.STRIPE_WEBHOOK_SECRET,
        ) = originals

    return restore


def test_http_checkout_individual_route_returns_url():
    import stripe

    restore = _configure_stripe()
    original_create = stripe.checkout.Session.create
    stripe.checkout.Session.create = staticmethod(
        lambda **kw: {"url": "https://checkout.stripe.com/c/pay/http_test"}
    )
    try:
        with TestClient(app) as client:
            r = client.post(
                "/checkout/individual",
                json={"success_url": "https://app/ok", "cancel_url": "https://app/no"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["checkout_url"].startswith("https://checkout.stripe.com/")
    finally:
        stripe.checkout.Session.create = original_create
        restore()


def test_http_webhook_completed_creates_user_via_route():
    import stripe

    restore = _configure_stripe()
    # Bypass real signature crypto: return our event dict from construct_event.
    event = _completed_event("cus_http_route", "http_buyer@example.com", "enterprise")
    original_construct = stripe.Webhook.construct_event
    stripe.Webhook.construct_event = staticmethod(lambda payload, sig, secret: dict(event))
    try:
        with TestClient(app) as client:
            r = client.post(
                "/webhook/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=deadbeef"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["result"]["action"] == "created"

            users = client.get("/users", headers={"X-Admin-Key": "test-admin-key"}).json()
            match = [u for u in users if u["stripe_customer_id"] == "cus_http_route"]
            assert len(match) == 1
            assert match[0]["plan_type"] == "enterprise"
            assert match[0]["days_remaining"] > 150
    finally:
        stripe.Webhook.construct_event = original_construct
        restore()


def test_http_webhook_disabled_without_secret_returns_503():
    # Safe local fallback: no webhook secret -> 503, never a crash.
    original = stripe_config.STRIPE_WEBHOOK_SECRET
    stripe_config.STRIPE_WEBHOOK_SECRET = ""
    try:
        with TestClient(app) as client:
            r = client.post(
                "/webhook/stripe",
                content=b"{}",
                headers={"stripe-signature": "x"},
            )
            assert r.status_code == 503
    finally:
        stripe_config.STRIPE_WEBHOOK_SECRET = original


# ---------------------------------------------------------------------------
# Direct runner (no pytest required)
# ---------------------------------------------------------------------------
def _run_all():
    setup_module(None)
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            import traceback

            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failures}/{len(tests)} passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
