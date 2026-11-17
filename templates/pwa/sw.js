// Service worker di Tana (D-22): l'app si installa ma serve la rete. Nessun contenuto in cache
// tranne la pagina che avvisa quando la rete manca.
const CACHE = "tana-senza-rete-v1";
const PAGINA = "{% url 'senza_rete' %}";

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.add(PAGINA)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nomi) => Promise.all(nomi.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (evento) => {
  if (evento.request.mode !== "navigate") return;
  evento.respondWith(fetch(evento.request).catch(() => caches.match(PAGINA)));
});
