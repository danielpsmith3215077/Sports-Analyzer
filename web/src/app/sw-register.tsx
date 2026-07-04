"use client";

import { useEffect } from "react";

/**
 * Registers the PWA service worker (web only). The worker file lives at
 * /service-worker.js in web/public and provides the offline launch shell.
 */
export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
      return;
    }
    const register = () => {
      navigator.serviceWorker.register("/service-worker.js").catch(() => {
        /* registration is best-effort; ignore failures */
      });
    };
    if (document.readyState === "complete") {
      register();
    } else {
      window.addEventListener("load", register);
      return () => window.removeEventListener("load", register);
    }
  }, []);

  return null;
}
