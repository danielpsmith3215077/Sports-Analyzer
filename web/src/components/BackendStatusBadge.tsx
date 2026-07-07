"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL, apiUrl } from "@/lib/api";

type Status = "checking" | "online" | "offline";

const POLL_INTERVAL_MS = 15_000;
const FETCH_TIMEOUT_MS = 5_000;

const STATUS_STYLES: Record<Status, string> = {
  checking:
    "bg-zinc-100 text-zinc-700 border-zinc-300 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700",
  online:
    "bg-green-50 text-green-800 border-green-300 dark:bg-green-950 dark:text-green-300 dark:border-green-800",
  offline:
    "bg-red-50 text-red-800 border-red-300 dark:bg-red-950 dark:text-red-300 dark:border-red-800",
};

const STATUS_LABEL: Record<Status, string> = {
  checking: "Checking\u2026",
  online: "Connected",
  offline: "Offline",
};

const STATUS_EMOJI: Record<Status, string> = {
  checking: "\u26AA",
  online: "\uD83D\uDFE2",
  offline: "\uD83D\uDD34",
};

/**
 * Live backend connectivity badge. Polls GET /api/healthcheck (zero-overhead
 * keep-alive route) against NEXT_PUBLIC_API_BASE_URL so the UI visibly
 * reflects whether the Render-hosted FastAPI engine is actually reachable.
 */
export default function BackendStatusBadge() {
  const [status, setStatus] = useState<Status>("checking");
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    const checkHealth = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
      try {
        const res = await fetch(apiUrl("/api/healthcheck"), {
          method: "GET",
          signal: controller.signal,
          cache: "no-store",
        });
        if (!mountedRef.current) return;
        setStatus(res.ok ? "online" : "offline");
      } catch {
        if (mountedRef.current) setStatus("offline");
      } finally {
        clearTimeout(timeout);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, POLL_INTERVAL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="flex flex-col items-center gap-1 sm:items-start">
      <span
        role="status"
        aria-live="polite"
        className={`inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium shadow-sm transition-colors ${STATUS_STYLES[status]}`}
      >
        <span aria-hidden="true">{STATUS_EMOJI[status]}</span>
        Backend Connection: {STATUS_LABEL[status]}
      </span>
      <span className="text-xs text-zinc-400 dark:text-zinc-600">
        {API_BASE_URL}
      </span>
    </div>
  );
}
