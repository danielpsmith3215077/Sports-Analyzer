# Sports Analyzer — Security Architecture

Multi-layered defense-in-depth for the Sports Analyzer platform, aligned with
**Zero Trust** (never trust, always verify) and **Least Privilege** (minimum
access required per component).

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Network & Infrastructure                                     │
│  Render/Vercel edge TLS + DDoS │ UFW (self-hosted) │ Docker isolation   │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 2 — Reverse Proxy & WAF                                        │
│  nginx rate limits + UA block │ Cloudflare WAF (optional)               │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 3 — Application Security                                       │
│  FastAPI middleware │ Pydantic validation │ CORS │ Next.js headers      │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 4 — DevSecOps & Supply Chain                                   │
│  pip-audit │ npm audit │ bandit │ gitleaks │ Dependabot                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

| Surface | Stack | Hosting | Auth model |
|---------|-------|---------|------------|
| API | FastAPI | Render | `X-Admin-Key` for admin; public validate/checkout/webhook |
| Marketing site | Next.js static | Vercel | No secrets in bundle; admin key entered at runtime |
| Dashboard | Streamlit | Render | License token via `license_gate.py` |
| Admin UI | Next.js `/admin` + Streamlit | Vercel + Render | API key + optional dashboard password |
| Database | Supabase Postgres | Supabase | Server-side `DATABASE_URL` only |
| Payments | Stripe | Stripe-hosted | Webhook signature verification |

## Threat model

| Threat | Layer | Control |
|--------|-------|---------|
| Internet-wide port scan | L1 | Render/Vercel expose 443 only; UFW on self-hosted |
| DDoS / request flood | L1/L2/L3 | Edge scrubbing + nginx rate limits + `backend/rate_limit.py` |
| Scanner bots (sqlmap, nikto) | L2/L3 | nginx UA maps + `RequestGuardMiddleware` UA blocklist |
| SQL injection | L3 | Parameterized queries (`backend/db.py`) + WAF query blocks |
| Admin key brute force | L3 | `secrets.compare_digest` + strict admin rate limits |
| Open user creation (POST /users) | L3 | `require_admin_key` on all `/users` routes |
| CORS data exfiltration | L3 | Project-scoped origin allowlist in `backend/main.py` |
| Stripe webhook forgery | L3 | `stripe.Webhook.construct_event` signature check |
| Oversized request bodies | L3 | `MAX_BODY_SIZE_BYTES` middleware cap |
| XSS on marketing site | L3 | CSP in `web/next.config.ts` |
| Clickjacking | L2/L3 | `X-Frame-Options: DENY` |
| Supply-chain vulns | L4 | `pip-audit`, `npm audit`, Dependabot |
| Secret leakage in git | L4 | gitleaks in CI |
| Token enumeration | L3 | `/validate` rate limits + token format validation |

## Directory layout

```
security/
├── README.md                 ← this file
├── ufw/setup-ufw.sh          ← host firewall (self-hosted)
├── docker/network-policies.yml
├── nginx/
│   ├── nginx.conf            ← reverse proxy
│   └── waf-rules.conf        ← map-based WAF rules
├── cloudflare/
│   ├── waf-rules.md          ← optional Cloudflare setup
│   └── ruleset.json          ← API/Terraform reference
├── render/README.md          ← Render hardening guide
└── dependabot.yml            ← copy also at .github/dependabot.yml

backend/
├── security_middleware.py    ← headers, UA block, body size, WAF-lite
├── rate_limit.py             ← IP-based rate limiting
└── admin_auth.py             ← timing-safe API key check

.github/workflows/security.yml
SECURITY.md                   ← vulnerability reporting
```

## Application controls (Layer 3)

### FastAPI middleware stack

Registered in `backend/main.py` (outermost first):

1. **CORS** — project-scoped origins only
2. **RequestGuardMiddleware** — body size, UA block, query WAF-lite, rate limits
3. **SecurityHeadersMiddleware** — HSTS, CSP, X-Frame-Options, etc.

### Public vs protected routes

| Route | Auth required |
|-------|---------------|
| `GET /api/healthcheck` | No |
| `GET /validate/{token}` | No (rate-limited) |
| `POST /checkout/*` | No (rate-limited) |
| `POST /webhook/stripe` | Stripe signature |
| `POST /users`, `GET /users`, `/admin/*`, `/enterprise/*` | `X-Admin-Key` |

### Environment variables

See `backend/.env.example` for the full list. Key security vars:

| Variable | Default | Purpose |
|----------|---------|---------|
| `RATE_LIMIT_ENABLED` | `true` | Master switch for rate limiting |
| `RATE_LIMIT_REQUESTS` | `120` | General API requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | General window |
| `RATE_LIMIT_ADMIN_REQUESTS` | `30` | Admin route cap |
| `MAX_BODY_SIZE_BYTES` | `1048576` | 1 MB body limit |
| `REDIS_URL` | (unset) | Shared rate-limit store (multi-instance) |
| `CORS_EXTRA_ORIGINS` | (unset) | Comma-separated extra allowed origins |
| `ENABLE_API_DOCS` | (unset) | Set `true` to expose `/docs` in dev |

## Streamlit limitations

Streamlit (`app.py`, `admin_dashboard.py`) does **not** support custom middleware.
Security relies on:

- Render edge TLS
- `license_gate.py` token validation against the API
- `ADMIN_DASHBOARD_PASSWORD` for the admin Streamlit page
- Network isolation when self-hosted (nginx proxy, no direct port exposure)

For production hardening, prefer the Next.js admin UI (`/admin`) which talks to
the hardened FastAPI layer.

## Deployment checklist

### Render (API)

- [ ] `ADMIN_API_KEY` set (long random, `sync: false`)
- [ ] `DATABASE_URL` points to Supabase (not exposed client-side)
- [ ] `STRIPE_WEBHOOK_SECRET` matches Stripe dashboard endpoint
- [ ] Health check path: `/api/healthcheck`
- [ ] Review Render metrics for 401/429 spikes after deploy

### Vercel (web)

- [ ] `NEXT_PUBLIC_API_BASE_URL=https://sportsanalyzer-api.onrender.com`
- [ ] No `ADMIN_API_KEY` in `NEXT_PUBLIC_*` vars
- [ ] Security headers applied via `web/vercel.json` (static export ignores `next.config.ts` headers)
- [ ] Verify: `curl -I https://sportsanalyzer-web.vercel.app`

### Stripe

- [ ] Webhook endpoint: `https://sportsanalyzer-api.onrender.com/webhook/stripe`
- [ ] Events: `checkout.session.completed`, `invoice.payment_failed`, `customer.subscription.deleted`
- [ ] Signing secret matches `STRIPE_WEBHOOK_SECRET`

### CI

- [ ] `.github/workflows/security.yml` passing on main
- [ ] Dependabot PRs reviewed weekly

### Optional (self-hosted / Cloudflare)

- [ ] `security/ufw/setup-ufw.sh` on VM
- [ ] `security/nginx/nginx.conf` with TLS certs
- [ ] Cloudflare WAF rules from `security/cloudflare/waf-rules.md`

## Testing security locally

```bash
# Disable rate limits for local dev (optional)
export RATE_LIMIT_ENABLED=false

# Run Stripe integration tests (SQLite, no live Supabase)
pytest backend/test_stripe_integration.py

# Postgres tests (requires isolated TEST_DATABASE_URL)
TEST_DATABASE_URL="postgresql://..." pytest backend/test_backend.py
```

## Incident response (summary)

1. **Revoke** compromised keys (`ADMIN_API_KEY`, Stripe, Supabase) immediately.
2. **Redeploy** Render services after env var rotation.
3. **Review** Supabase audit logs and Stripe webhook delivery logs.
4. **Block** offending IPs at Cloudflare/nginx if self-hosted.
5. Report via [SECURITY.md](../SECURITY.md) process if third-party discovered.
