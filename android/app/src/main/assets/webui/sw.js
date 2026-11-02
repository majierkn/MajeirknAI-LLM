/* Service worker da Majeirkn AI.
   A interface funciona offline (cache do shell); a API nunca e cacheada. */
var CACHE = "majeirkn-ui-v1";
var SHELL = [
  "./",
  "./index.html",
  "./app.js",
  "./style.css",
  "./manifest.json",
  "./system.txt",
  "./icons/icon-192.png",
  "./icons/icon-512.png"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      // addAll falha tudo se um arquivo nao existir: adiciona um a um.
      return Promise.all(
        SHELL.map(function (url) {
          return cache.add(new Request(url, { cache: "reload" }))
            .catch(function () { return undefined; });
        })
      );
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names.map(function (name) {
          if (name !== CACHE) { return caches.delete(name); }
          return undefined;
        })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

function isApi(url) {
  return (
    url.pathname.indexOf("/v1/") === 0 ||
    url.pathname.indexOf("/health") === 0 ||
    url.pathname.indexOf("/props") === 0 ||
    url.pathname.indexOf("/slots") === 0 ||
    url.pathname.indexOf("/tokenize") === 0
  );
}

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") { return; }  // POST de chat: sempre rede

  var url = new URL(request.url);
  if (isApi(url)) { return; }  // respostas do modelo nunca vem do cache

  event.respondWith(
    caches.match(request).then(function (hit) {
      if (hit) { return hit; }
      return fetch(request).then(function (response) {
        if (response && response.ok && url.origin === self.location.origin) {
          var copy = response.clone();
          caches.open(CACHE).then(function (cache) { cache.put(request, copy); });
        }
        return response;
      });
    })
  );
});
