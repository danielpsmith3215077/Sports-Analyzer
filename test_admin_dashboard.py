"""
test_admin_dashboard.py
Health + interpretation suite for the admin control tower.

Verifies that admin_dashboard.py:
  * compiles and imports cleanly (layout libraries load, no import/syntax gaps),
  * exposes its expected callables,
  * computes the SaaS business metrics correctly (active, pending renewals,
    paused, MRR with the $29 / $199 placeholder constants),
  * filters the subscriber grid by name / email / plan_type / status.

No backend or Streamlit runtime is required: the module is import-safe because
all UI rendering is guarded behind `__name__ == "__main__"`.

Run:
    pytest test_admin_dashboard.py
    # or directly:
    python3 test_admin_dashboard.py
"""

import importlib
import py_compile
import sys


def test_compiles_without_syntax_errors():
    py_compile.compile("admin_dashboard.py", doraise=True)


def test_imports_without_errors_and_exposes_api():
    mod = importlib.import_module("admin_dashboard")
    for attr in ("main", "require_password", "render_dashboard", "compute_metrics", "filter_users"):
        assert hasattr(mod, attr), f"admin_dashboard is missing {attr}"


def test_default_mrr_price_constants():
    mod = importlib.import_module("admin_dashboard")
    assert mod.INDIVIDUAL_MONTHLY_PRICE == 29
    assert mod.ENTERPRISE_MONTHLY_PRICE == 199


def _sample_users():
    return [
        {"id": "1", "name": "Ann", "email": "ann@x.com", "plan_type": "individual",
         "status": "active", "days_remaining": 120},
        {"id": "2", "name": "Bob", "email": "bob@x.com", "plan_type": "individual",
         "status": "active", "days_remaining": 3},   # pending renewal
        {"id": "3", "name": "Cid", "email": "cid@corp.com", "plan_type": "enterprise",
         "status": "active", "days_remaining": 200},
        {"id": "4", "name": "Dee", "email": "dee@x.com", "plan_type": "individual",
         "status": "paused", "days_remaining": 50},
        {"id": "5", "name": "Eve", "email": "eve@x.com", "plan_type": "enterprise",
         "status": "revoked", "days_remaining": 0},
    ]


def test_compute_metrics():
    mod = importlib.import_module("admin_dashboard")
    m = mod.compute_metrics(_sample_users())
    assert m["total_active"] == 3            # Ann, Bob, Cid
    assert m["pending_renewals"] == 1        # Bob (3 days <= 7)
    assert m["paused"] == 1                  # Dee
    assert m["active_individual"] == 2       # Ann, Bob
    assert m["active_enterprise"] == 1       # Cid
    # MRR = 2 * 29 + 1 * 199 = 257
    assert m["estimated_mrr"] == 2 * 29 + 1 * 199


def test_compute_metrics_custom_prices():
    mod = importlib.import_module("admin_dashboard")
    m = mod.compute_metrics(_sample_users(), individual_price=49, enterprise_price=499)
    assert m["estimated_mrr"] == 2 * 49 + 1 * 499


def test_filter_by_search():
    mod = importlib.import_module("admin_dashboard")
    users = _sample_users()
    assert len(mod.filter_users(users, search="corp")) == 1          # email match
    assert len(mod.filter_users(users, search="enterprise")) == 2    # plan match
    assert len(mod.filter_users(users, search="paused")) == 1        # status match
    assert len(mod.filter_users(users, search="ann")) == 1           # name match


def test_filter_by_status_and_plan():
    mod = importlib.import_module("admin_dashboard")
    users = _sample_users()
    assert len(mod.filter_users(users, statuses=["active"])) == 3
    assert len(mod.filter_users(users, plans=["enterprise"])) == 2
    assert len(mod.filter_users(users, statuses=["active"], plans=["individual"])) == 2


def _run_all():
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
