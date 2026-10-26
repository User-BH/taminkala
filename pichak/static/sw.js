/* سرویس‌ورکر برنامه‌ی «استعلام چک تامین کالا»
   فقط برای نصب روی صفحه‌ی گوشی و پیام آفلاین؛ هیچ پاسخ استعلامی (/api/) کش نمی‌شود. */
var CACHE = 'pichak-shell-v1';
var SHELL = ['/', '/static/fallback.css', '/static/vendor/bootstrap.rtl.min.css', '/static/vendor/html5-qrcode.min.js?v=4', '/logo.png', '/static/icon-192.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).catch(function () {}).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin || url.pathname.indexOf('/api/') === 0) return;   // استعلام همیشه زنده
  // صفحه و فایل‌ها: اول شبکه (همیشه آخرین نسخه)، اگر اینترنت نبود از کش
  e.respondWith(fetch(req).then(function (res) {
    if (res.ok && (req.mode === 'navigate' || SHELL.indexOf(url.pathname + url.search) !== -1)) {
      var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req.mode === 'navigate' ? '/' : req, copy); });
    }
    return res;
  }).catch(function () {
    return caches.match(req.mode === 'navigate' ? '/' : req).then(function (hit) {
      return hit || new Response('اتصال اینترنت برقرار نیست؛ دوباره تلاش کنید.', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    });
  }));
});
