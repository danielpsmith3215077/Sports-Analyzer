"use client";

import { useEffect, useState } from "react";

/**
 * Shows a one-time banner after returning from Stripe checkout
 * (?checkout=success|cancel), matching the success_url/cancel_url
 * CheckoutButton sends. Reads window.location directly since this is a
 * static export with no server-side routing.
 */
export default function CheckoutStatusBanner() {
  const [status, setStatus] = useState<"success" | "cancel" | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const checkout = params.get("checkout");
    if (checkout === "success" || checkout === "cancel") {
      setStatus(checkout);
    }
  }, []);

  if (!status) return null;

  if (status === "success") {
    return (
      <div className="w-full max-w-2xl rounded-xl border border-green-300 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300">
        Payment received — check your email for your access token, then paste
        it below to open the dashboard.
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl rounded-xl border border-zinc-300 bg-zinc-50 px-4 py-3 text-sm text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
      Checkout was cancelled — no charge was made. Pick a plan below whenever
      you&apos;re ready.
    </div>
  );
}
