/**
 * Opens a URL appropriately for the current runtime.
 *
 * - In the Capacitor mobile app (native iOS/Android), navigating the app's
 *   own webview to an external domain (Stripe checkout, the Streamlit
 *   dashboard) breaks the experience — there's no browser chrome, and
 *   success/cancel redirect URLs built from window.location.origin would
 *   point at the app's internal capacitor:// origin instead of a real
 *   domain. So on native we launch the system/in-app browser instead via
 *   @capacitor/browser, keeping the webview intact.
 * - In a normal web browser, a plain location change works fine.
 */
export async function openExternal(url: string, { replace = false } = {}) {
  const { Capacitor } = await import("@capacitor/core");
  if (Capacitor.isNativePlatform()) {
    const { Browser } = await import("@capacitor/browser");
    await Browser.open({ url });
    return;
  }
  if (replace) {
    window.location.href = url;
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

/** True when running inside the Capacitor native app shell (not a browser tab). */
export async function isNativeApp(): Promise<boolean> {
  const { Capacitor } = await import("@capacitor/core");
  return Capacitor.isNativePlatform();
}
