import type { NextConfig } from "next";
import path from "path";

/**
 * Security headers for the static-export marketing site.
 * Threat mitigations:
 *   - CSP: blocks XSS / rogue script injection on the static front door
 *   - HSTS: forces HTTPS on repeat visits
 *   - X-Frame-Options: prevents clickjacking of checkout/admin flows
 *   - Permissions-Policy: disables unused browser APIs in the marketing shell
 */
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ||
  "https://sportsanalyzer-api.onrender.com";

const DASHBOARD_BASE =
  process.env.NEXT_PUBLIC_DASHBOARD_URL?.replace(/\/+$/, "") ||
  "https://sportsanalyzer-dashboard.onrender.com";

const securityHeaders = [
  {
    key: "X-DNS-Prefetch-Control",
    value: "on",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "Permissions-Policy",
    value:
      "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
  },
  {
    key: "X-XSS-Protection",
    value: "0",
  },
  {
    // Allow API + dashboard + Stripe checkout redirects; deny inline scripts except Next bootstrap.
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      `connect-src 'self' ${API_BASE} ${DASHBOARD_BASE} https://api.stripe.com`,
      "frame-src https://checkout.stripe.com https://js.stripe.com",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self' https://checkout.stripe.com",
      "upgrade-insecure-requests",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  // Static export: emits web/out (plain HTML/CSS/JS, no Node server) so the
  // Capacitor mobile shell can bundle it directly as its webDir.
  output: "export",
  // next/image's default loader requires the Node image-optimization server,
  // which doesn't exist in a static export — serve images as-is instead.
  images: {
    unoptimized: true,
  },
  // Pin the workspace root to this app dir so Next stops inferring an
  // ancestor directory when multiple lockfiles exist on the machine.
  turbopack: {
    root: path.resolve(__dirname),
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
