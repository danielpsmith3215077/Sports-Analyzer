"use client";

import { dashboardUrl, DEMO_ACCESS_TOKEN } from "@/lib/api";
import { openExternal } from "@/lib/openExternal";

/**
 * One-click investor demo — opens the Streamlit dashboard with the shared
 * demo access token (no password entry required).
 */
export default function DemoAccessButton({
  label = "View Live Demo",
  className = "bg-emerald-600 text-white hover:bg-emerald-500",
}: {
  label?: string;
  className?: string;
}) {
  const handleClick = () => {
    if (!DEMO_ACCESS_TOKEN) {
      console.error("NEXT_PUBLIC_DEMO_ACCESS_TOKEN is not configured");
      return;
    }
    void openExternal(dashboardUrl(DEMO_ACCESS_TOKEN));
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={!DEMO_ACCESS_TOKEN}
      className={`rounded-full px-6 py-3 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {label}
    </button>
  );
}
