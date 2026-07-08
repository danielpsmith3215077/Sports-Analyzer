"""
Set Render service environment variables via the Render REST API.
Reads RENDER_API_KEY and target values from .env.local (never prints secrets).

Usage:
    python scripts/render_set_env.py sportsanalyzer-api DATABASE_URL DEMO_ACCESS_TOKEN
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def _api(method: str, path: str, body: dict | None = None) -> object:
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        raise SystemExit("RENDER_API_KEY is not set")
    data = None
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"https://api.render.com/v1{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise SystemExit(f"Render API {method} {path} failed ({e.code}): {err}") from e


def _find_service_id(name: str) -> str:
    cursor = ""
    while True:
        qs = f"?limit=20&name={name}"
        if cursor:
            qs += f"&cursor={cursor}"
        payload = _api("GET", f"/services{qs}")
        for item in payload or []:
            svc = item.get("service") or item
            if svc.get("name") == name:
                return svc["id"]
        cursor = (payload[-1].get("cursor") if payload else "") or ""
        if not cursor:
            break
    raise SystemExit(f"Service not found: {name}")


def _upsert_env(service_id: str, key: str, value: str) -> None:
    existing = _api("GET", f"/services/{service_id}/env-vars")
    env_id = None
    for item in existing or []:
        ev = item.get("envVar") or item
        if ev.get("key") == key:
            env_id = ev["id"]
            break
    if env_id:
        _api("PUT", f"/services/{service_id}/env-vars/{env_id}", {"value": value})
        print(f"[render] Updated {key} on {service_id}")
    else:
        _api(
            "POST",
            f"/services/{service_id}/env-vars",
            {"key": key, "value": value},
        )
        print(f"[render] Created {key} on {service_id}")


def main() -> int:
    _load_env_local()
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    service_name = sys.argv[1]
    keys = sys.argv[2:]
    service_id = _find_service_id(service_name)
    print(f"[render] Service {service_name} -> {service_id}")
    for key in keys:
        value = os.environ.get(key, "").strip()
        if not value:
            print(f"[render] SKIP {key} (not set locally)", file=sys.stderr)
            continue
        _upsert_env(service_id, key, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
