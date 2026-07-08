# Render deployment hardening — Sports Analyzer

Render manages TLS termination, DDoS scrubbing, and edge routing for all three
web services in `render.yaml`. This document covers **platform-specific**
controls you should apply in the Render dashboard.

## Services

| Service | URL | Role |
|---------|-----|------|
| `sportsanalyzer-api` | https://sportsanalyzer-api.onrender.com | FastAPI — licensing, Stripe, admin |
| `sportsanalyzer-dashboard` | https://sportsanalyzer-dashboard.onrender.com | Streamlit product UI |
| `sportsanalyzer-admin` | https://sportsanalyzer-admin.onrender.com | Streamlit admin (optional) |

## Network posture (managed by Render)

- **TLS 1.2+** terminated at Render's edge — HSTS reinforced by app middleware.
- **No SSH/shell access** to containers — host-level UFW (`security/ufw/`) is
  for future self-hosted deploys only.
- **Health check** pinned to `/api/healthcheck` — keeps the free tier awake
  without exposing admin routes.

## Environment secrets (least privilege)

Set these in **Render Dashboard → Environment** with `sync: false` (never in git):

| Variable | Service | Notes |
|----------|---------|-------|
| `DATABASE_URL` | api | Supabase Postgres async URL |
| `ADMIN_API_KEY` | api, admin | Long random string; `secrets.compare_digest` on server |
| `STRIPE_SECRET_KEY` | api | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | api | Webhook signing secret — signature verified on every POST |
| `STRIPE_*_PRICE_ID` | api | Subscription price IDs |
| `ADMIN_DASHBOARD_PASSWORD` | admin | Streamlit UI gate (separate from API key) |
| `DEMO_ACCESS_TOKEN` | dashboard | Investor demo only |
| `RATE_LIMIT_*` | api | Optional tuning (see `backend/.env.example`) |
| `REDIS_URL` | api | Optional — shared rate-limit counters across instances |

### Rotation checklist

1. Generate new secret in provider dashboard (Stripe, Supabase, Render).
2. Update Render env var → save → wait for auto-redeploy.
3. Revoke old secret at source.
4. Verify `/admin/verify` and `/webhook/stripe` still succeed.

## Render-specific controls to enable

1. **Auto-deploy from main only** — disable deploys from unreviewed branches.
2. **Notification webhooks** — alert on failed deploys (supply-chain signal).
3. **Custom domain + Cloudflare** (optional) — put Cloudflare in front of
   Render for WAF rules in `security/cloudflare/waf-rules.md`.
4. **Do not expose** internal service ports; only public HTTPS URLs above.

## Public route allowlist (Zero Trust)

Only these paths should be reachable without `X-Admin-Key`:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/`, `/api/healthcheck` | Keep-alive / status |
| GET | `/validate/{token}` | License check (rate-limited) |
| POST | `/checkout/individual`, `/checkout/enterprise` | Stripe session creation |
| POST | `/webhook/stripe` | Stripe signed webhooks |

All `/users`, `/admin`, `/enterprise` routes require `X-Admin-Key`.

## Stripe webhook hardening

- Endpoint URL: `https://sportsanalyzer-api.onrender.com/webhook/stripe`
- Stripe Dashboard → Webhooks → select events:
  - `checkout.session.completed`
  - `invoice.payment_failed`
  - `customer.subscription.deleted`
- **Always** verify `stripe-signature` header (implemented in `backend/main.py`).
- Never disable signature verification in production.

## Vercel (frontend)

The Next.js static site on Vercel is a separate surface:

- Set `NEXT_PUBLIC_API_BASE_URL=https://sportsanalyzer-api.onrender.com`
- Security headers configured in `web/next.config.ts`
- No server-side secrets in the static export — admin key entered client-side
  and sent only over HTTPS to the API

## Monitoring

- Render **Metrics** tab: watch 4xx/5xx spikes (possible scan or brute force).
- Supabase **Logs**: failed auth / connection errors.
- Stripe **Webhook logs**: delivery failures or signature mismatches.

## Self-hosted alternative

If you migrate off Render, use:

1. `security/ufw/setup-ufw.sh` on the VM
2. `security/nginx/nginx.conf` as reverse proxy
3. `security/docker/network-policies.yml` for container isolation
