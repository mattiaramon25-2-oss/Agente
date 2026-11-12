// Service worker minimo: serve solo a rendere la chat installabile come app.
// Nessuna cache: tutte le richieste vanno alla rete, /api/ compreso.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (evento) => evento.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (evento) => {
  if (new URL(evento.request.url).pathname.startsWith('/api/')) return;
  evento.respondWith(fetch(evento.request));
});
