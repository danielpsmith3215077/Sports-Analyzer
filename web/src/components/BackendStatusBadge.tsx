"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL, apiUrl } from "@/lib/api";

type Status = "checking" | "online" | "offline";

const POLL_INTERVAL_MS = 15_000;
const FETCH_TIMEOUT_MS = 5_000;

const STATUS_LABEL: Record<Status, string> = {
  checking: "Checking",
  online: "Connected",
  offline: "Offline",
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
    <div className="flex flex-col items-start gap-1.5">
      <span
        role="status"
        aria-live="polite"
        className={`sa-status sa-status--${status}`}
      >
        <span className="sa-status__dot" aria-hidden="true" />
        Engine {STATUS_LABEL[status]}
      </span>
      <span className="max-w-[min(100%,18rem)] truncate text-[0.65rem] tracking-wide text-[var(--muted)]">
        {API_BASE_URL}
      </span>
    </div>
  );
}
