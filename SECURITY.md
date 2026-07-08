# Security Policy

## Supported versions

| Component | Supported | Notes |
|-----------|-----------|-------|
| `sportsanalyzer-api` (FastAPI) | ✅ Active | https://sportsanalyzer-api.onrender.com |
| `sportsanalyzer-web` (Next.js) | ✅ Active | https://sportsanalyzer-web.vercel.app |
| `sportsanalyzer-dashboard` (Streamlit) | ✅ Active | Render |
| Mobile (Capacitor) | ✅ Active | iOS / Android wrappers |

## Reporting a vulnerability

If you discover a security issue in Sports Analyzer, please report it responsibly.

**Do NOT** open a public GitHub issue for security vulnerabilities.

### Preferred contact

Email: **security@sportsanalyzer.app** (or open a private security advisory on GitHub if enabled for this repository).

Include:

1. Description of the vulnerability
2. Steps to reproduce
3. Impact assessment (data exposure, privilege escalation, etc.)
4. Affected component (API, web, dashboard, mobile)
5. Your contact info for follow-up (optional)

### What to expect

| Timeline | Action |
|----------|--------|
| 48 hours | Acknowledgment of your report |
| 7 days | Initial triage and severity assessment |
| 30 days | Target fix for confirmed high/critical issues |
| 90 days | Coordinated disclosure (or sooner if fixed) |

We will credit reporters who wish to be acknowledged, unless you prefer anonymity.

## Scope

**In scope:**

- Authentication and authorization bypass (`X-Admin-Key`, license validation)
- SQL injection, XSS, CSRF on any Sports Analyzer surface
- Stripe webhook signature bypass
- Secret exposure in client bundles or public repos
- Rate-limit / DoS weaknesses with demonstrable impact
- Supabase data access beyond intended RLS boundaries

**Out of scope:**

- Social engineering attacks
- Denial of service requiring impractical resource levels
- Issues in third-party services (Stripe, Render, Vercel, Supabase) — report to them directly
- Missing security headers on domains we do not control

## Safe harbor

We will not pursue legal action against researchers who:

- Make a good-faith effort to avoid privacy violations and service disruption
- Do not access, modify, or delete data belonging to other users
- Report findings promptly and allow reasonable time for remediation

## Security architecture

See [`security/README.md`](security/README.md) for the full defense-in-depth model,
threat matrix, and deployment checklist.
