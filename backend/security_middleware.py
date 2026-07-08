"""
backend/security_middleware.py
Application-layer security controls for the FastAPI API.

Layers implemented here (Zero Trust / defense-in-depth):
  1. Request body size cap        — mitigates large-payload DoS
  2. Malicious User-Agent block   — stops automated scanners (sqlmap, nikto…)
  3. Security response headers    — HSTS, CSP, clickjacking, MIME sniffing
  4. Input sanitization helpers   — strips control chars before DB writes
"""

from __future__ import annotations

import os
import re
from typing import Callable

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.rate_limit import enforce_rate_limit

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_BODY_SIZE_BYTES: int = int(os.environ.get("MAX_BODY_SIZE_BYTES", str(1 * 1024 * 1024)))

# HSTS max-age: 1 year (only sent over HTTPS in production)
HSTS_MAX_AGE: int = int(os.environ.get("HSTS_MAX_AGE_SECONDS", "31536000"))

# Content-Security-Policy for JSON API responses (browsers shouldn't render these,
# but CSP still limits any accidental HTML/script injection paths).
API_CSP: str = os.environ.get(
    "API_CONTENT_SECURITY_POLICY",
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
)

# Scanner / exploit-tool User-Agent substrings (case-insensitive).
# Threat: automated vulnerability scanners probing public endpoints.
_BLOCKED_UA_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"sqlmap",
        r"nikto",
        r"nmap",
        r"masscan",
        r"nessus",
        r"openvas",
        r"acunetix",
        r"dirbuster",
        r"gobuster",
        r"wfuzz",
        r"hydra",
        r"metasploit",
        r"burpsuite",
        r"owasp",
        r"w3af",
        r"arachni",
        r"skipfish",
        r"httpx",          # ProjectDiscovery scanner (not the HTTP/2 lib)
        r"nuclei",
        r"feroxbuster",
    )
)

# Paths exempt from UA blocking (Stripe webhooks use Stripe's own UA string).
_UA_EXEMPT_PATHS = frozenset({"/webhook/stripe", "/api/healthcheck"})

# Control characters except tab/newline/carriage-return (OWASP input validation).
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Common SQLi / path-traversal probe patterns in query strings.
_SUSPICIOUS_QUERY_RE = re.compile(
    r"(union\s+select|/\.\./|;\s*drop\s+table|<script|javascript:|onerror\s*=)",
    re.IGNORECASE,
)


def sanitize_text(value: str | None, *, max_length: int | None = None) -> str | None:
    """
    Strip control characters and enforce optional max length before persistence.
    Threat: log injection, stored XSS in admin UIs, binary garbage in names.
    """
    if value is None:
        return None
    cleaned = _CONTROL_CHAR_RE.sub("", value).strip()
    if max_length is not None and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned or None


def sanitize_email_local(value: str) -> str:
    """Normalize email: lowercase domain-safe cleanup without breaking EmailStr validation."""
    return _CONTROL_CHAR_RE.sub("", value).strip().lower()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard hardening headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        response.headers["Content-Security-Policy"] = API_CSP
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # HSTS only when the request arrived over TLS (Render terminates TLS at edge).
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if forwarded_proto == "https" or request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={HSTS_MAX_AGE}; includeSubDomains; preload"
            )

        return response


class RequestGuardMiddleware(BaseHTTPMiddleware):
    """
    Pre-handler guards: body size, User-Agent blocklist, suspicious query strings,
    and per-IP rate limiting.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # --- Suspicious query-string probes (WAF-lite at app layer) ---
        raw_query = str(request.url.query)
        if raw_query and _SUSPICIOUS_QUERY_RE.search(raw_query):
            return JSONResponse(
                status_code=400,
                content={"detail": "Malformed request"},
            )

        # --- User-Agent blocklist ---
        if path not in _UA_EXEMPT_PATHS:
            ua = request.headers.get("user-agent", "")
            if ua and any(pat.search(ua) for pat in _BLOCKED_UA_PATTERNS):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden"},
                )

        # --- Request body size (Content-Length pre-check) ---
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > MAX_BODY_SIZE_BYTES:
                        return JSONResponse(
                            status_code=413,
                            content={"detail": f"Request body exceeds {MAX_BODY_SIZE_BYTES} byte limit"},
                        )
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})

        # --- Rate limiting ---
        try:
            enforce_rate_limit(request)
        except HTTPException as exc:
            if exc.status_code == 429:
                return JSONResponse(
                    status_code=429,
                    content={"detail": exc.detail},
                    headers=exc.headers or {},
                )
            raise

        return await call_next(request)
