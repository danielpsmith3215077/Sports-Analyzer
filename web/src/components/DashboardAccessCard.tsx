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
    <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
        Already have access?
      </h3>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
        Paste the access token from your welcome email to open the prediction
        dashboard.
      </p>
      <form
        className="mt-4 flex flex-col gap-3 sm:flex-row"
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
          className="flex-1 rounded-full border border-zinc-300 bg-transparent px-4 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:text-zinc-50"
        />
        <button
          type="submit"
          className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Open Dashboard
        </button>
      </form>
    </div>
  );
}
