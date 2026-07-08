#!/usr/bin/env bash
# security/ufw/setup-ufw.sh
#
# Host-level firewall for self-hosted Sports Analyzer deployments.
# Render and Vercel manage edge firewalls for managed services — run this
# script only on VMs you control (e.g. future bare-metal or VPS deploy).
#
# Threat mitigated: shrink attack surface to SSH + HTTP/S only; rate-limit SSH
# brute-force attempts.
#
# Usage (as root):
#   sudo bash security/ufw/setup-ufw.sh
#
# Prerequisites: ufw installed (apt install ufw / yum install ufw)

set -euo pipefail

if [[ "${EUID:-}" -ne 0 ]]; then
  echo "ERROR: run as root (sudo bash $0)" >&2
  exit 1
fi

echo "==> Resetting UFW to known-good defaults"
ufw --force reset

echo "==> Default deny inbound, allow outbound (Zero Trust network posture)"
ufw default deny incoming
ufw default allow outgoing

echo "==> Allow SSH (22) with connection rate limiting"
ufw limit 22/tcp comment 'SSH rate-limited'

echo "==> Allow HTTP/HTTPS (80/443) for nginx reverse proxy"
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

echo "==> Deny all other inbound ports"
# FastAPI (8000) and Streamlit (8501) must NOT be public — nginx proxies them.

echo "==> Enabling UFW"
ufw --force enable

echo "==> Status:"
ufw status verbose

echo ""
echo "Done. Verify:"
echo "  - ssh still works from your IP"
echo "  - nginx listens on 80/443 only"
echo "  - uvicorn/streamlit bind 127.0.0.1 (not 0.0.0.0) behind nginx"
