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
    <div className="w-full max-w-md rounded-2xl border border-[#2d3348] bg-[#1a1d29] p-6">
      <h3 className="text-lg font-semibold text-zinc-50">
        Already have access?
      </h3>
      <p className="mt-1 text-sm text-zinc-400">
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
          className="flex-1 rounded-full border border-[#2d3348] bg-[#0e1117] px-4 py-2 text-sm text-zinc-50 outline-none focus:border-[#4c8dd6]"
        />
        <button
          type="submit"
          className="rounded-full bg-[#4c8dd6] px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#3a7bc0]"
        >
          Open Dashboard
        </button>
      </form>
    </div>
  );
}
