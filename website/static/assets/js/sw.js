const CACHE_NAME = 'logo-cache-v1';

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
  );
});

self.addEventListener('fetch', function(event) {
  if (event.request.url.includes('/candidate/get_logo_urls') ||
      event.request.url.includes('logo')) {
    event.respondWith(
      caches.open(CACHE_NAME).then(function(cache) {
        return fetch(event.request).then(function(response) {
          cache.put(event.request, response.clone());
          return response;
        }).catch(function() {
          return cache.match(event.request);
        });
      })
    );
  }
});

console.log('Service Worker loaded');