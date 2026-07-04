"""
backend/stripe_config.py
Central Stripe configuration. Every secret is read from an environment
variable — nothing is ever hardcoded.

If a required variable is missing at boot we emit a clear console ERROR alert
but do NOT crash: the app gracefully falls back to safe local test behavior
(checkout/webhook endpoints return HTTP 503 "not configured" instead of
attempting live calls). This keeps local dev, CI, and the prediction engine
fully runnable without Stripe credentials.

Compliance note (Apple App Store Guideline 3.1.3(b) — Multiplatform Services):
All monetization here is WEB-ONLY. Checkout Sessions, price selection, and card
management happen exclusively through Stripe-hosted web URLs; the mobile wrapper
never presents in-app purchase UI and simply reads the license entitlement
granted after a web purchase. See backend/main.py checkout routers.
"""

import logging
import os

import stripe

logger = logging.getLogger("stripe_config")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_INDIVIDUAL_PRICE_ID = os.environ.get("STRIPE_INDIVIDUAL_PRICE_ID", "")
STRIPE_ENTERPRISE_PRICE_ID = os.environ.get("STRIPE_ENTERPRISE_PRICE_ID", "")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def _warn_if_missing():
    missing = [
        name
        for name, val in [
            ("STRIPE_SECRET_KEY", STRIPE_SECRET_KEY),
            ("STRIPE_WEBHOOK_SECRET", STRIPE_WEBHOOK_SECRET),
            ("STRIPE_INDIVIDUAL_PRICE_ID", STRIPE_INDIVIDUAL_PRICE_ID),
            ("STRIPE_ENTERPRISE_PRICE_ID", STRIPE_ENTERPRISE_PRICE_ID),
        ]
        if not val
    ]
    if missing:
        # Ensure the alert is visible even if the host app hasn't configured
        # logging handlers yet.
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO)
        logger.error(
            "Missing Stripe environment variable(s): %s. Checkout and webhook "
            "endpoints are DISABLED and will return HTTP 503; falling back to "
            "safe local test behavior. The rest of the API runs normally.",
            ", ".join(missing),
        )


_warn_if_missing()


def is_configured() -> bool:
    """True only if the secret key + both price IDs are present (enough to sell)."""
    return bool(
        STRIPE_SECRET_KEY
        and STRIPE_INDIVIDUAL_PRICE_ID
        and STRIPE_ENTERPRISE_PRICE_ID
    )


def price_id_for_plan(plan_type: str) -> str:
    return {
        "individual": STRIPE_INDIVIDUAL_PRICE_ID,
        "enterprise": STRIPE_ENTERPRISE_PRICE_ID,
    }.get(plan_type, "")


def plan_for_price_id(price_id: str) -> str:
    """Reverse map a Stripe price ID back to our plan_type. Defaults to
    'individual' if the price ID is unrecognized/absent."""
    if price_id and price_id == STRIPE_ENTERPRISE_PRICE_ID:
        return "enterprise"
    if price_id and price_id == STRIPE_INDIVIDUAL_PRICE_ID:
        return "individual"
    return "individual"
