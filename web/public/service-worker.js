/*
 * service-worker.js
 * Minimal offline shell cache for the Sports Analyzer PWA. The prediction
 * dashboard itself is served dynamically by the app host; this SW just makes
 * the launch shell installable and resilient to flaky networks.
 */
const CACHE = "sports-analyzer-shell-v1";
const SHELL = [
  "/",
  "/index.html",
  "/manifest.json",
  "/app.js",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).catch(() => caches.match("/index.html")))
  );
});
