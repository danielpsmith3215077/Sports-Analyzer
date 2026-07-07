"""
admin_dashboard.py
Standalone administrative control tower for the Sports Analyzer SaaS.

A distinct Streamlit application (run it on its own port) that reads from the
Milestone 1 licensing backend and provides visual oversight + per-user license
controls (pause / resume / revoke).

Run:
    export ADMIN_DASHBOARD_PASSWORD="choose-a-strong-password"
    streamlit run admin_dashboard.py --server.port 8503

Point it at a non-default backend with:
    export SAAS_API_URL="http://localhost:8000"

Design note: all Streamlit rendering lives inside main(), invoked only under
`__name__ == "__main__"` (which is how `streamlit run` executes a script). This
keeps the module import-safe for the validator suite (test_admin_dashboard.py),
so importing it never triggers UI or network calls.
"""

import os
from datetime import datetime, timezone

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_URL = os.environ.get("SAAS_API_URL", "http://localhost:8000").rstrip("/")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "").strip()


def _admin_headers() -> dict:
    """Attach X-Admin-Key when ADMIN_API_KEY is configured."""
    if not ADMIN_API_KEY:
        return {}
    return {"X-Admin-Key": ADMIN_API_KEY}

# --- Configurable placeholder pricing (used ONLY for the MRR estimate) -----
# Clearly exposed and modifiable; override via env vars if desired.
INDIVIDUAL_MONTHLY_PRICE = float(os.environ.get("INDIVIDUAL_MONTHLY_PRICE", "29"))
ENTERPRISE_MONTHLY_PRICE = float(os.environ.get("ENTERPRISE_MONTHLY_PRICE", "199"))

# Licenses expiring within this many days are counted as "Pending Renewals".
RENEWAL_WINDOW_DAYS = int(os.environ.get("RENEWAL_WINDOW_DAYS", "7"))


# ---------------------------------------------------------------------------
# Pure logic (no Streamlit / no network) — unit-testable
# ---------------------------------------------------------------------------
def _days_remaining(user: dict) -> int:
    """Prefer the backend-computed value; fall back to expires_at if absent."""
    if user.get("days_remaining") is not None:
        try:
            return int(user["days_remaining"])
        except (TypeError, ValueError):
            pass
    exp = user.get("expires_at")
    if not exp:
        return 0
    try:
        dt = exp if isinstance(exp, datetime) else datetime.fromisoformat(str(exp))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = (dt - datetime.now(timezone.utc)).total_seconds()
        return int(secs // 86400) if secs > 0 else 0
    except (ValueError, TypeError):
        return 0


def compute_metrics(
    users,
    individual_price: float = INDIVIDUAL_MONTHLY_PRICE,
    enterprise_price: float = ENTERPRISE_MONTHLY_PRICE,
    renewal_window_days: int = RENEWAL_WINDOW_DAYS,
) -> dict:
    """Aggregate the global SaaS business metrics from a list of user dicts."""
    active = [u for u in users if u.get("status") == "active"]
    paused = [u for u in users if u.get("status") == "paused"]

    pending_renewals = [
        u for u in active if 0 <= _days_remaining(u) <= renewal_window_days
    ]

    active_individual = sum(1 for u in active if u.get("plan_type") == "individual")
    active_enterprise = sum(1 for u in active if u.get("plan_type") == "enterprise")
    mrr = active_individual * individual_price + active_enterprise * enterprise_price

    return {
        "total_active": len(active),
        "pending_renewals": len(pending_renewals),
        "paused": len(paused),
        "active_individual": active_individual,
        "active_enterprise": active_enterprise,
        "estimated_mrr": mrr,
    }


def filter_users(users, search: str = "", statuses=None, plans=None):
    """Filter by free-text (name/email/plan_type/status) + optional status/plan
    multiselect. Returns a new list."""
    search = (search or "").strip().lower()
    statuses = set(statuses or [])
    plans = set(plans or [])

    def matches(u):
        if statuses and u.get("status") not in statuses:
            return False
        if plans and u.get("plan_type") not in plans:
            return False
        if search:
            haystack = " ".join(
                str(u.get(k, "") or "")
                for k in ("name", "email", "plan_type", "status")
            ).lower()
            if search not in haystack:
                return False
        return True

    return [u for u in users if matches(u)]


# ---------------------------------------------------------------------------
# Backend API helpers
# ---------------------------------------------------------------------------
def fetch_users():
    try:
        resp = requests.get(f"{API_URL}/users", headers=_admin_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json(), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def api_post(path):
    return requests.post(f"{API_URL}{path}", headers=_admin_headers(), timeout=10)


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
def require_password() -> bool:
    """Freeze everything behind the ADMIN_DASHBOARD_PASSWORD gate."""
    import streamlit as st

    expected = os.environ.get("ADMIN_DASHBOARD_PASSWORD", "")
    if not expected:
        st.error(
            "ADMIN_DASHBOARD_PASSWORD is not set on the server. Set it in the "
            "environment before launching this dashboard."
        )
        return False

    if st.session_state.get("admin_authed"):
        return True

    st.title("🛠️ Admin Login")
    st.caption("Enter the administrator password to unlock the control tower.")
    pw = st.text_input("Admin password", type="password")
    if st.button("Sign in", type="primary"):
        if pw == expected:
            st.session_state["admin_authed"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


def _flash(resp, verb):
    import streamlit as st

    if resp.status_code == 200:
        st.session_state["_flash"] = ("success", f"{verb} successfully.")
    else:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:  # noqa: BLE001
            detail = resp.text
        st.session_state["_flash"] = ("error", f"{verb} failed: {detail}")


def render_dashboard():
    import streamlit as st

    st.title("🛠️ Sports Analyzer — Admin Control Tower")
    st.caption(f"Backend API: {API_URL}")

    top = st.columns([1, 1, 6])
    if top[0].button("🔄 Refresh"):
        st.rerun()
    if top[1].button("Log out"):
        st.session_state.pop("admin_authed", None)
        st.rerun()

    users, err = fetch_users()
    if err:
        st.error(
            f"Could not reach the backend API at {API_URL}. Is it running?\n\n"
            f"Start it with: `uvicorn backend.main:app --port 8000`\n\nDetails: {err}"
        )
        return
    if not users:
        st.info("No users yet. Create some via the backend API or a Stripe checkout.")
        return

    # --- Summary metrics deck ---------------------------------------------
    metrics = compute_metrics(users)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Active Users", metrics["total_active"])
    m2.metric(f"Pending Renewals (≤{RENEWAL_WINDOW_DAYS}d)", metrics["pending_renewals"])
    m3.metric("Paused / Suspended", metrics["paused"])
    m4.metric("Estimated MRR", f"${metrics['estimated_mrr']:,.0f}")
    st.caption(
        f"MRR = individual ${INDIVIDUAL_MONTHLY_PRICE:.0f}/mo × {metrics['active_individual']} "
        f"+ enterprise ${ENTERPRISE_MONTHLY_PRICE:.0f}/mo × {metrics['active_enterprise']}. "
        f"Prices are configurable placeholders (INDIVIDUAL_MONTHLY_PRICE / "
        f"ENTERPRISE_MONTHLY_PRICE env vars)."
    )

    st.divider()

    # --- Filters -----------------------------------------------------------
    f1, f2, f3 = st.columns([3, 2, 2])
    search = f1.text_input("Search (name, email, plan, status)").strip()
    all_statuses = sorted({u.get("status", "") for u in users if u.get("status")})
    all_plans = sorted({u.get("plan_type", "") for u in users if u.get("plan_type")})
    status_filter = f2.multiselect("Status", options=all_statuses, default=[])
    plan_filter = f3.multiselect("Plan", options=all_plans, default=[])

    view = filter_users(users, search, status_filter, plan_filter)

    # id -> name for showing the parent enterprise nicely.
    id_to_name = {u["id"]: u.get("name") for u in users}

    # --- Read-only data grid ----------------------------------------------
    st.subheader(f"Subscribers ({len(view)})")
    if view:
        table_rows = [
            {
                "name": u.get("name"),
                "email": u.get("email"),
                "plan_type": u.get("plan_type"),
                "status": u.get("status"),
                "days_remaining": _days_remaining(u),
                "parent_enterprise": id_to_name.get(u.get("parent_enterprise_id"), ""),
            }
            for u in view
        ]
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No subscribers match the current filters.")
        return

    st.divider()
    st.subheader("License controls")

    # --- Per-row operational control console ------------------------------
    for u in view:
        uid = str(u["id"])
        status = u.get("status")
        c = st.columns([3, 2, 2, 1, 1, 1])
        c[0].markdown(f"**{u.get('name') or '—'}**  \n{u.get('email')}")
        c[1].write(f"Plan: `{u.get('plan_type')}`")
        c[2].write(f"Status: `{status}` · {_days_remaining(u)}d left")

        if c[3].button("Pause", key=f"pause_{uid}", disabled=status == "revoked"):
            _flash(api_post(f"/users/{uid}/pause"), "Paused")
            st.rerun()
        if c[4].button("Resume", key=f"resume_{uid}", disabled=status == "revoked"):
            _flash(api_post(f"/users/{uid}/resume"), "Resumed")
            st.rerun()
        if c[5].button("Revoke", key=f"revoke_{uid}", type="secondary"):
            _flash(api_post(f"/users/{uid}/revoke"), "Revoked")
            st.rerun()


def main():
    import streamlit as st

    st.set_page_config(page_title="Sports Analyzer — Admin", page_icon="🛠️", layout="wide")

    if require_password():
        flash = st.session_state.pop("_flash", None)
        if flash:
            kind, msg = flash
            (st.success if kind == "success" else st.error)(msg)
        render_dashboard()


# `streamlit run admin_dashboard.py` executes this module as "__main__".
if __name__ == "__main__":
    main()
