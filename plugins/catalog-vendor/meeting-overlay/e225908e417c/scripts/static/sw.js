const CACHE = 'meeting-pwa-v1'
self.addEventListener('install', e => {
  self.skipWaiting()
})
self.addEventListener('activate', e => {
  e.waitUntil(clients.claim())
})
// network-first: the panel is live data; cache nothing, just make it installable
self.addEventListener('fetch', e => {
  e.respondWith(fetch(e.request).catch(() => new Response('', { status: 503 })))
})