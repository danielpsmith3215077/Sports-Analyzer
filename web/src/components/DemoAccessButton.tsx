"use client";

import { dashboardUrl, DEMO_ACCESS_TOKEN } from "@/lib/api";
import { openExternal } from "@/lib/openExternal";

/**
 * One-click investor demo — opens the Streamlit dashboard with the shared
 * demo access token (no password entry required).
 */
export default function DemoAccessButton({
  label = "View Live Demo",
  className = "sa-btn sa-btn-secondary",
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
      className={`disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {label}
    </button>
  );
}
