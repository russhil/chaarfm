const CACHE_NAME = 'chaar-fm-v2';
const ASSETS_TO_CACHE = [
    '/',
    '/static/css/style.css',
    '/static/js/player.js',
    '/static/images/logo-192.png',
    '/static/manifest.json'
];

self.addEventListener('install', (event) => {
    // Skip waiting - activate immediately
    self.skipWaiting();

    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

self.addEventListener('activate', (event) => {
    // Claim clients immediately
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Don't cache API calls or streams
    if (event.request.url.includes('/api/') || event.request.url.includes('/stream/')) {
        return;
    }

    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});
