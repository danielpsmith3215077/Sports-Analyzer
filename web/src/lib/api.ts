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
