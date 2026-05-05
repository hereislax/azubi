// Service Worker – Azubi PWA
const CACHE_NAME = 'azubi-v1';

const PRECACHE_URLS = [
    '/',
];

// Install: Precache wichtige Ressourcen
self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(PRECACHE_URLS);
        }).then(function () {
            return self.skipWaiting();
        })
    );
});

// Activate: Alte Caches entfernen
self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys().then(function (names) {
            return Promise.all(
                names.filter(function (name) { return name !== CACHE_NAME; })
                     .map(function (name) { return caches.delete(name); })
            );
        }).then(function () {
            return self.clients.claim();
        })
    );
});

// Fetch: Strategie je nach Request-Typ
self.addEventListener('fetch', function (event) {
    var request = event.request;

    // Nur GET-Requests cachen
    if (request.method !== 'GET') return;

    // Keine Admin-, API- oder Auth-Requests cachen
    var url = new URL(request.url);
    if (url.pathname.startsWith('/admin/') ||
        url.pathname.startsWith('/accounts/')) {
        return;
    }

    // Statische Assets: Cache-first
    if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
        event.respondWith(
            caches.match(request).then(function (cached) {
                if (cached) return cached;
                return fetch(request).then(function (response) {
                    if (response.ok) {
                        var clone = response.clone();
                        caches.open(CACHE_NAME).then(function (cache) {
                            cache.put(request, clone);
                        });
                    }
                    return response;
                });
            })
        );
        return;
    }

    // HTML-Seiten: Network-first mit Cache-Fallback
    if (request.headers.get('Accept') && request.headers.get('Accept').includes('text/html')) {
        event.respondWith(
            fetch(request).then(function (response) {
                if (response.ok) {
                    var clone = response.clone();
                    caches.open(CACHE_NAME).then(function (cache) {
                        cache.put(request, clone);
                    });
                }
                return response;
            }).catch(function () {
                return caches.match(request);
            })
        );
        return;
    }
});
