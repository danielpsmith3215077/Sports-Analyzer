"""
license_gate.py
Reusable Streamlit access gate for the main Sports Analyzer app. It validates a
license access token against the SaaS backend on EVERY rerun so that a paused
or revoked account loses access on its very next interaction.

Usage (put near the top of app.py, after st.set_page_config):
    from license_gate import enforce_license
    enforce_license()   # halts the app (st.stop) unless a valid token is present

Environment:
    SAAS_API_URL  backend base URL (default http://localhost:8000)
    APP_URL       this app's public URL, used for Stripe success/cancel redirects
                  (default http://localhost:8501)
"""

import os

import requests
import streamlit as st

API_URL = os.environ.get("SAAS_API_URL", "http://localhost:8000").rstrip("/")
APP_URL = os.environ.get("APP_URL", "http://localhost:8501").rstrip("/")

_TOKEN_KEY = "access_token"


def _validate(token: str):
    """Returns the backend's /validate payload, or None if unreachable."""
    try:
        resp = requests.get(f"{API_URL}/validate/{token}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001
        return None


def _get_checkout_url(plan_type: str):
    try:
        resp = requests.post(
            f"{API_URL}/checkout/{plan_type}",
            json={
                "success_url": f"{APP_URL}/?checkout=success",
                "cancel_url": f"{APP_URL}/?checkout=cancel",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("checkout_url"), None
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:  # noqa: BLE001
            detail = resp.text
        return None, detail
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def _render_checkout_options():
    st.subheader("Purchase access")
    st.write(
        "Choose a plan to start a subscription. After checkout you'll receive an "
        "access token to paste above."
    )
    # Web-only billing (Apple Guideline 3.1.3(b) Multiplatform Services): these
    # buttons open Stripe-hosted web checkout. The mobile wrapper never shows an
    # in-app purchase form — it links out to the web to activate a license.
    st.caption("Secure billing is handled on the web via Stripe-hosted checkout.")
    c1, c2 = st.columns(2)
    for col, plan, label in [
        (c1, "individual", "Individual plan"),
        (c2, "enterprise", "Enterprise plan"),
    ]:
        with col:
            url, err = _get_checkout_url(plan)
            if url:
                st.link_button(f"Subscribe — {label}", url, use_container_width=True)
            else:
                st.button(
                    f"Subscribe — {label} (unavailable)",
                    disabled=True,
                    use_container_width=True,
                    key=f"cb_{plan}",
                )
                st.caption(f"Checkout unavailable: {err}")


def _render_gate(error_message: str | None = None):
    st.title("🔒 Sports Analyzer — Access Required")
    if error_message:
        st.error(error_message)

    # Allow a token to arrive via ?token=... in the URL (e.g. from the access link).
    prefill = ""
    try:
        prefill = st.query_params.get("token", "") or ""
    except Exception:  # noqa: BLE001
        prefill = ""

    with st.form("license_form"):
        token = st.text_input(
            "Access token", value=prefill, type="password",
            placeholder="Paste your access token",
        )
        submitted = st.form_submit_button("Unlock", type="primary")
    if submitted and token.strip():
        st.session_state[_TOKEN_KEY] = token.strip()
        st.rerun()

    st.divider()
    _render_checkout_options()
    st.stop()


def enforce_license():
    """Gate the app. Returns the validation payload if access is valid;
    otherwise renders the gate and halts execution via st.stop()."""
    # Adopt a token from the URL on first load if none is in session yet.
    if _TOKEN_KEY not in st.session_state:
        try:
            url_token = st.query_params.get("token", "")
        except Exception:  # noqa: BLE001
            url_token = ""
        if url_token:
            st.session_state[_TOKEN_KEY] = url_token

    token = st.session_state.get(_TOKEN_KEY)
    if not token:
        _render_gate()
        return None  # unreachable (st.stop) but keeps type-checkers happy

    # Re-validate on EVERY rerun so pause/revoke take effect immediately.
    result = _validate(token)
    if result is None:
        _render_gate(
            f"Could not reach the licensing server at {API_URL}. "
            "Please try again shortly."
        )
        return None

    if not result.get("valid"):
        status = result.get("status", "invalid")
        st.session_state.pop(_TOKEN_KEY, None)
        _render_gate(f"This access token is not valid (status: {status}).")
        return None

    # Valid — show a small expiry caption and a log-out control in the sidebar.
    days = result.get("days_remaining", 0)
    st.caption(f"✅ Access valid · plan: {result.get('plan_type', '?')} · expires in {days} days")
    with st.sidebar:
        st.markdown("### Account")
        st.write(f"Plan: `{result.get('plan_type', '?')}`")
        st.write(f"Expires in **{days}** days")
        if st.button("Log out"):
            st.session_state.pop(_TOKEN_KEY, None)
            st.rerun()
    return result
