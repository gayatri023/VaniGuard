// Minimal service worker: makes the app installable. It deliberately caches nothing,
// so participants always get the current build and no audio or API data is ever stored.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
