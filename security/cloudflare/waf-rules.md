# Cloudflare WAF — optional edge rules for Sports Analyzer

Use this when you place **Cloudflare** in front of Render (`sportsanalyzer-api`,
`sportsanalyzer-dashboard`) or Vercel (`sportsanalyzer-web.vercel.app`).

Render and Vercel already provide TLS and basic DDoS protection. Cloudflare
adds a second WAF layer, bot management, and geo-blocking if needed.

## Setup (one-time)

1. Add your domain to Cloudflare (or use Cloudflare for SaaS with Vercel).
2. Point DNS A/CNAME records to Render/Vercel origins (orange-cloud proxied).
3. SSL/TLS mode: **Full (strict)**.
4. Enable **Bot Fight Mode** (free) or **Super Bot Fight Mode** (Pro).
5. Import rules below in **Security → WAF → Custom rules**.

## Custom WAF rules (Cloudflare dashboard)

Create these as **Custom rules** (expression → action):

### 1. Block scanner User-Agents

```
(http.user_agent contains "sqlmap") or
(http.user_agent contains "nikto") or
(http.user_agent contains "nmap") or
(http.user_agent contains "masscan") or
(http.user_agent contains "acunetix") or
(http.user_agent contains "nessus") or
(http.user_agent contains "nuclei") or
(http.user_agent contains "gobuster") or
(http.user_agent contains "dirbuster")
```

**Action:** Block

### 2. Block SQLi in query string

```
(http.request.uri.query contains "union select") or
(http.request.uri.query contains "1=1") or
(http.request.uri.query contains "drop table") or
(http.request.uri.query contains "<script") or
(http.request.uri.query contains "javascript:")
```

**Action:** Block

### 3. Block path traversal

```
(http.request.uri.path contains "../") or
(http.request.uri.path contains "%2e%2e") or
(http.request.uri.path contains "/etc/passwd") or
(http.request.uri.path contains ".env") or
(http.request.uri.path contains ".git")
```

**Action:** Block

### 4. Rate-limit admin routes

**Expression:**

```
(http.request.uri.path starts with "/users") or
(http.request.uri.path starts with "/admin") or
(http.request.uri.path starts with "/enterprise")
```

**Action:** Rate limit — 30 requests / 60 seconds / IP

### 5. Allow Stripe webhooks (bypass bot fight)

**Expression:**

```
(http.request.uri.path eq "/webhook/stripe") and
(http.request.method eq "POST")
```

**Action:** Skip → All remaining custom rules (or add IP allowlist for
[Stripe webhook IPs](https://stripe.com/docs/ips) if using managed challenge).

## Managed rulesets (recommended)

Enable these Cloudflare managed rulesets:

| Ruleset | Purpose |
|---------|---------|
| Cloudflare OWASP Core Ruleset | SQLi, XSS, RCE patterns |
| Cloudflare Exposed Credentials Check | Leaked credential detection |
| Cloudflare Bot Management (if available) | Automated abuse |

## Rate limiting rules

| Rule | Path | Threshold |
|------|------|-----------|
| Validate tokens | `/validate/*` | 60 req/min/IP |
| Checkout | `/checkout/*` | 20 req/min/IP |
| General API | `*` | 120 req/min/IP |

## Security headers (Transform Rules)

If not already set by the app, add **Response headers** transform:

| Header | Value |
|--------|-------|
| Strict-Transport-Security | `max-age=31536000; includeSubDomains; preload` |
| X-Content-Type-Options | `nosniff` |
| X-Frame-Options | `DENY` |
| Referrer-Policy | `strict-origin-when-cross-origin` |

> Note: Vercel and the FastAPI middleware already emit these — avoid duplicate
> conflicting values; use Cloudflare only for gaps.

## JSON ruleset export (API / Terraform reference)

See `ruleset.json` for a machine-readable snapshot of the custom rules above.
Import via Cloudflare API or Terraform `cloudflare_ruleset` resource.

## What Cloudflare does NOT replace

- `ADMIN_API_KEY` verification on admin routes (app layer)
- Stripe `stripe-signature` verification (app layer)
- Supabase RLS / parameterized queries (data layer)
- Secret rotation in Render dashboard
