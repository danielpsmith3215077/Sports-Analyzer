/**
 * Central API base-URL resolution for the Sports Analyzer web frontend.
 *
 * In production (Vercel) set NEXT_PUBLIC_API_BASE_URL to the live Render API
 * deployment URL, e.g. https://sportsanalyzer-api.onrender.com
 * Locally it falls back to the dev FastAPI server on localhost:8000.
 *
 * NEXT_PUBLIC_* variables are inlined at build time, so this value must be
 * present in the Vercel project's Environment Variables for production builds.
 */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000";

/** Build a fully-qualified API URL from a path (e.g. apiUrl("/api/healthcheck")). */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * The actual product UI (Streamlit dashboard: fighter picker, Monte Carlo
 * simulation, six-layer model breakdown) lives on its own Render service,
 * gated by license_gate.py against the API above. This site is the
 * marketing/checkout front door that hands licensed users off to it.
 */
export const DASHBOARD_URL: string =
  process.env.NEXT_PUBLIC_DASHBOARD_URL?.replace(/\/+$/, "") ||
  "http://localhost:8501";

/** Build a dashboard URL, optionally pre-filling the access token query param. */
export function dashboardUrl(accessToken?: string): string {
  if (!accessToken) return DASHBOARD_URL;
  return `${DASHBOARD_URL}/?token=${encodeURIComponent(accessToken)}`;
}

/**
 * The public web origin for this marketing site itself. Used for Stripe
 * checkout success/cancel redirects when running inside the native mobile
 * app, where window.location.origin is an internal capacitor:// scheme that
 * Stripe can't usefully redirect back to.
 */
export const SITE_URL: string =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/+$/, "") ||
  "https://sportsanalyzer-web.vercel.app";

/** Shareable investor demo token — inlined at build time from Vercel env. */
export const DEMO_ACCESS_TOKEN: string =
  process.env.NEXT_PUBLIC_DEMO_ACCESS_TOKEN?.trim() || "";
