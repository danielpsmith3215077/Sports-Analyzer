"""
backend/rate_limit.py
IP-based request rate limiting for the FastAPI API layer.

Threat mitigated: credential stuffing, brute-force admin key guessing,
Stripe webhook replay floods, and general DoS at the application tier.

Uses an in-memory sliding window by default. Set REDIS_URL to share counters
across multiple uvicorn workers or Render instances (optional).
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable

from fastapi import HTTPException, Request

# ---------------------------------------------------------------------------
# Configuration (override via environment)
# ---------------------------------------------------------------------------
def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


RATE_LIMIT_ENABLED: bool = _env_bool("RATE_LIMIT_ENABLED", True)

# Default bucket: general API traffic
RATE_LIMIT_REQUESTS: int = int(os.environ.get("RATE_LIMIT_REQUESTS", "120"))
RATE_LIMIT_WINDOW_SECONDS: int = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Stricter bucket for admin routes (mitigates admin-key brute force)
RATE_LIMIT_ADMIN_REQUESTS: int = int(os.environ.get("RATE_LIMIT_ADMIN_REQUESTS", "30"))
RATE_LIMIT_ADMIN_WINDOW_SECONDS: int = int(
    os.environ.get("RATE_LIMIT_ADMIN_WINDOW_SECONDS", "60")
)

# Checkout endpoints (mitigates Stripe session spam)
RATE_LIMIT_CHECKOUT_REQUESTS: int = int(
    os.environ.get("RATE_LIMIT_CHECKOUT_REQUESTS", "20")
)
RATE_LIMIT_CHECKOUT_WINDOW_SECONDS: int = int(
    os.environ.get("RATE_LIMIT_CHECKOUT_WINDOW_SECONDS", "60")
)

# Validate endpoint (token enumeration)
RATE_LIMIT_VALIDATE_REQUESTS: int = int(
    os.environ.get("RATE_LIMIT_VALIDATE_REQUESTS", "60")
)
RATE_LIMIT_VALIDATE_WINDOW_SECONDS: int = int(
    os.environ.get("RATE_LIMIT_VALIDATE_WINDOW_SECONDS", "60")
)

REDIS_URL: str = os.environ.get("REDIS_URL", "").strip()

# Trusted proxies — only these may set X-Forwarded-For (Render, Vercel edge)
_TRUSTED_PROXY_CIDRS = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                        "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                        "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                        "172.30.", "172.31.", "192.168.", "100.64.", "127.")


@dataclass
class RateLimitRule:
    """A named rate-limit bucket with its own window and cap."""
    name: str
    max_requests: int
    window_seconds: int
    path_matcher: Callable[[str], bool]


def _is_admin_path(path: str) -> bool:
    return path.startswith("/admin") or path.startswith("/users") or path.startswith(
        "/enterprise"
    )


def _is_checkout_path(path: str) -> bool:
    return path.startswith("/checkout")


def _is_validate_path(path: str) -> bool:
    return path.startswith("/validate")


DEFAULT_RULES: list[RateLimitRule] = [
    RateLimitRule("admin", RATE_LIMIT_ADMIN_REQUESTS, RATE_LIMIT_ADMIN_WINDOW_SECONDS, _is_admin_path),
    RateLimitRule("checkout", RATE_LIMIT_CHECKOUT_REQUESTS, RATE_LIMIT_CHECKOUT_WINDOW_SECONDS, _is_checkout_path),
    RateLimitRule("validate", RATE_LIMIT_VALIDATE_REQUESTS, RATE_LIMIT_VALIDATE_WINDOW_SECONDS, _is_validate_path),
    RateLimitRule("default", RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS, lambda _: True),
]


def resolve_client_ip(request: Request) -> str:
    """
    Extract the client IP, honoring X-Forwarded-For only when the direct peer
    looks like an internal/trusted proxy (Render load balancer).
    """
    direct = request.client.host if request.client else "unknown"
    if not any(direct.startswith(prefix) for prefix in _TRUSTED_PROXY_CIDRS):
        return direct

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # Left-most entry is the original client per RFC 7239 de-facto convention.
        return forwarded.split(",")[0].strip()
    return direct


def _rule_for_path(path: str) -> RateLimitRule:
    for rule in DEFAULT_RULES:
        if rule.path_matcher(path) and rule.name != "default":
            return rule
    return DEFAULT_RULES[-1]


@dataclass
class _InMemoryBucket:
    timestamps: list[float] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)


class InMemoryRateLimiter:
    """Thread-safe sliding-window counter keyed by (rule, client_ip)."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _InMemoryBucket] = defaultdict(_InMemoryBucket)
        self._global_lock = Lock()

    def check(self, rule: RateLimitRule, client_ip: str) -> tuple[bool, int]:
        key = (rule.name, client_ip)
        now = time.monotonic()
        cutoff = now - rule.window_seconds

        with self._global_lock:
            bucket = self._buckets[key]

        with bucket.lock:
            bucket.timestamps = [t for t in bucket.timestamps if t > cutoff]
            if len(bucket.timestamps) >= rule.max_requests:
                retry_after = int(rule.window_seconds - (now - bucket.timestamps[0])) + 1
                return False, max(retry_after, 1)
            bucket.timestamps.append(now)
            remaining = rule.max_requests - len(bucket.timestamps)
            return True, remaining


class RedisRateLimiter:
    """
    Optional Redis-backed limiter for multi-worker deployments.
    Falls back to in-memory if redis package is unavailable.
    """

    def __init__(self, url: str) -> None:
        try:
            import redis  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "REDIS_URL is set but the 'redis' package is not installed"
            ) from exc
        self._client = redis.from_url(url, decode_responses=True)
        self._fallback = InMemoryRateLimiter()

    def check(self, rule: RateLimitRule, client_ip: str) -> tuple[bool, int]:
        key = f"rl:{rule.name}:{client_ip}"
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, rule.window_seconds)
            count, _ = pipe.execute()
            if int(count) > rule.max_requests:
                ttl = self._client.ttl(key)
                return False, max(int(ttl), 1)
            return True, rule.max_requests - int(count)
        except Exception:
            # Degrade gracefully — never take down the API because Redis blipped.
            return self._fallback.check(rule, client_ip)


_limiter: InMemoryRateLimiter | RedisRateLimiter | None = None


def get_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    global _limiter
    if _limiter is None:
        if REDIS_URL:
            try:
                _limiter = RedisRateLimiter(REDIS_URL)
            except RuntimeError:
                _limiter = InMemoryRateLimiter()
        else:
            _limiter = InMemoryRateLimiter()
    return _limiter


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency / middleware helper — raises 429 when exceeded."""
    if not RATE_LIMIT_ENABLED:
        return

    # Health checks and Stripe webhooks must never be rate-limited:
    # Render keep-alive and Stripe retry semantics depend on reliable 2xx/4xx.
    path = request.url.path
    if path in ("/", "/api/healthcheck", "/webhook/stripe"):
        return

    rule = _rule_for_path(path)
    client_ip = resolve_client_ip(request)
    allowed, meta = get_limiter().check(rule, client_ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(meta)},
        )
