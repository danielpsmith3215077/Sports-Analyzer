# Render free-tier keep-alive

Free Render services sleep after ~15 minutes of inactivity. Ping the health
endpoint every 10–14 minutes so cold starts don't break demos.

## Option A — GitHub Actions (recommended, automated)

Workflow: `.github/workflows/keepalive.yml`

- Schedule: every 12 minutes (`*/12 * * * *`)
- Pings: `https://sportsanalyzer-api.onrender.com/api/healthcheck`
- Also pings the dashboard (non-fatal if it fails)
- Manual run: GitHub → Actions → **Keep-alive** → **Run workflow**

No external account or API key required. Requires the workflow file on `main`.

## Option B — cron-job.org (no code)

1. Create a free job at https://cron-job.org
2. URL: `https://sportsanalyzer-api.onrender.com/api/healthcheck`
3. Schedule: every 10 minutes
4. Optional second job: `https://sportsanalyzer-dashboard.onrender.com/` (or its health path)

## Option C — local cron (Mac)

```bash
# crontab -e
*/10 * * * * curl -fsS https://sportsanalyzer-api.onrender.com/api/healthcheck >/dev/null
```

## Option D — one-liner watch (dev machine)

```bash
while true; do curl -fsS https://sportsanalyzer-api.onrender.com/api/healthcheck; sleep 600; done
```
