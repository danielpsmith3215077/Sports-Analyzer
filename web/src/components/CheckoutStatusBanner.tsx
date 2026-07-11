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
      <div className="sa-banner sa-banner--success">
        Payment received — check your email for your access token, then paste
        it below to open the dashboard.
      </div>
    );
  }

  return (
    <div className="sa-banner sa-banner--neutral">
      Checkout was cancelled — no charge was made. Pick a plan below whenever
      you&apos;re ready.
    </div>
  );
}
