// JARVIS como app de la pantalla de inicio: avisos propios y una pantalla
// amable cuando el Mac de JARVIS no responde. No guarda el panel en caché:
// siempre se ve la versión que sirve JARVIS.
const OFFLINE = '/offline.html';
const CACHE = 'jarvis-offline-v1';

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll([OFFLINE, '/apple-touch-icon.png'])));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE)));
  }
});

self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(self.registration.showNotification(data.title || 'JARVIS', {
    body: data.body || '',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: { url: data.url || '/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil((async () => {
    // Las rutas de navegación (Maps, Waze) se abren fuera; el resto, en JARVIS.
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    if (url.startsWith('/') && windows.length) {
      await windows[0].focus();
      return;
    }
    await self.clients.openWindow(url);
  })());
});
