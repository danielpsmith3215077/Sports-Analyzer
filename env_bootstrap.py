"""
env_bootstrap.py
Minimal .env.local loader shared by local entry points (app.py, admin_dashboard.py)
that don't run through a framework with built-in dotenv support. No third-party
dependency required.

On Render (or any host where real environment variables are already set via the
dashboard), this is a no-op for every key that's already present — os.environ
.setdefault() never overwrites a value that's already in the environment.
"""

import os


def load_env_local(filename: str = ".env.local") -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
