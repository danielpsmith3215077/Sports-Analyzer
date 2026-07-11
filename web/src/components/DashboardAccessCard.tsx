"use client";

import { useState } from "react";
import { dashboardUrl } from "@/lib/api";
import { openExternal } from "@/lib/openExternal";

/**
 * Hands off already-licensed users to the Streamlit dashboard (the actual
 * product UI), pre-filling their access token as a query param so
 * license_gate.py's enforce_license() unlocks it on load.
 */
export default function DashboardAccessCard() {
  const [token, setToken] = useState("");

  return (
    <section
      aria-labelledby="access-heading"
      className="sa-card mx-auto w-full max-w-lg"
    >
      <h3
        id="access-heading"
        className="sa-display text-2xl text-[var(--foreground)]"
      >
        Already licensed?
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
        Paste the access token from your welcome email to open the prediction
        dashboard.
      </p>
      <form
        className="mt-5 flex flex-col gap-3 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          if (!token.trim()) return;
          void openExternal(dashboardUrl(token.trim()));
        }}
      >
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Access token"
          className="sa-input flex-1"
        />
        <button type="submit" className="sa-btn sa-btn-primary shrink-0">
          Open Dashboard
        </button>
      </form>
    </section>
  );
}
