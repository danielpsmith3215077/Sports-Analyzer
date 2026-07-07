"use client";

import { useState } from "react";
import { apiUrl, SITE_URL } from "@/lib/api";
import { isNativeApp, openExternal } from "@/lib/openExternal";

type Plan = "individual" | "enterprise";

/**
 * Starts a Stripe-hosted checkout session for the given plan and redirects
 * the browser to it. Web-only billing (Apple Guideline 3.1.3(b)): this is
 * the sole purchase path — the mobile app wrapper never shows in-app
 * purchase UI, it just links here.
 */
export default function CheckoutButton({
  plan,
  label,
  className = "",
}: {
  plan: Plan;
  label: string;
  className?: string;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startCheckout = async () => {
    setLoading(true);
    setError(null);
    try {
      const native = await isNativeApp();
      // Native: redirect back to the real public site (a system/in-app
      // browser can land there); web: redirect back to this same tab.
      const origin = native ? SITE_URL : window.location.origin;
      const res = await fetch(apiUrl(`/checkout/${plan}`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          success_url: `${origin}/?checkout=success`,
          cancel_url: `${origin}/?checkout=cancel`,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.checkout_url) {
        throw new Error(data.detail || `Checkout unavailable (HTTP ${res.status})`);
      }
      // Web-only billing (Apple Guideline 3.1.3(b)): on native this opens the
      // system/in-app browser rather than navigating the app's own webview.
      await openExternal(data.checkout_url, { replace: true });
      if (native) setLoading(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={startCheckout}
        disabled={loading}
        className={`inline-flex items-center justify-center rounded-full px-6 py-3 text-sm font-semibold transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${className}`}
      >
        {loading ? "Redirecting to secure checkout…" : label}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
