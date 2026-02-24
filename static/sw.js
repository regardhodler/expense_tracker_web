// Minimal service worker — enables PWA install prompt.
// Does NOT cache app pages (Streamlit requires live WebSocket).
// Only caches static icon assets for faster loads.

const CACHE_NAME = "expense-tracker-v1";
const PRECACHE = [
  "/app/_statics/icon-192.png",
  "/app/_statics/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Only serve cached static assets; let everything else go to network
  if (event.request.url.includes("/app/_statics/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
