/*
 * app.js
 * PWA bootstrap + native-wrapper billing compliance.
 *
 * Compliance (Apple Guideline 3.1.3(b) — Multiplatform Services):
 * When running inside the Capacitor native wrapper we HIDE all in-app billing
 * UI and route purchases to the web checkout in the system browser, so the
 * native app ships fee-free and never presents in-app purchase forms.
 */

// The app's real dashboard host (Streamlit / Vercel). Override at build time.
const APP_URL = window.SPORTS_ANALYZER_APP_URL || "https://sports-analyzer.vercel.app";
const WEB_CHECKOUT_BASE = window.SPORTS_ANALYZER_CHECKOUT_BASE || APP_URL;

function isNative() {
  return !!(window.Capacitor && typeof window.Capacitor.isNativePlatform === "function"
    && window.Capacitor.isNativePlatform());
}

// Register the service worker (web/PWA only).
if ("serviceWorker" in navigator && !isNative()) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const launch = document.getElementById("launch");
  if (launch) launch.href = APP_URL;

  // Point checkout buttons at the web checkout endpoints.
  const ind = document.getElementById("checkout-individual");
  const ent = document.getElementById("checkout-enterprise");
  if (ind) ind.href = `${WEB_CHECKOUT_BASE}/checkout/individual`;
  if (ent) ent.href = `${WEB_CHECKOUT_BASE}/checkout/enterprise`;

  if (isNative()) {
    // Hide the in-app billing block on native targets.
    const billing = document.getElementById("billing");
    if (billing) billing.classList.add("native-hidden");

    // Open any external/checkout links in the system browser, not in-app.
    const openExternal = (url) => {
      if (window.Capacitor?.Plugins?.Browser) {
        window.Capacitor.Plugins.Browser.open({ url });
      } else {
        window.open(url, "_system");
      }
    };
    document.querySelectorAll("a[href^='http'], a[href*='/checkout/']").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        openExternal(a.href);
      });
    });
  }
});
