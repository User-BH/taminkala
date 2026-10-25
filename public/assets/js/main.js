/* تأمین کالا باختر — اسکریپت‌های سایت | طراحی و توسعه: شرکت رهوار پیوند داده */
(function () {
  'use strict';
  var root = document.documentElement;
  var KEY = 'tkb-theme';

  /* ---------- تم: پیش‌فرض روشن؛ انتخاب تاریک کاربر ذخیره می‌شود ---------- */
  function store(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function read() { try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'; } catch (e) { return 'light'; } }

  function applyTheme(theme) {
    if (theme === 'dark') root.setAttribute('data-theme', 'dark');
    else root.removeAttribute('data-theme');
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#15100e' : '#991522');
    var btn = document.getElementById('themeBtn');
    var label = theme === 'dark' ? 'حالت روشن' : 'حالت تاریک';
    btn.setAttribute('aria-label', 'رفتن به ' + label);
    btn.setAttribute('aria-pressed', theme === 'dark');
    btn.querySelector('.t-label').textContent = label;
  }
  applyTheme(read());
  document.getElementById('themeBtn').addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    store(next);
    applyTheme(next);
  });

  /* ---------- هدر و دکمه بازگشت به بالا ---------- */
  var header = document.querySelector('.site-header');
  var toTop = document.querySelector('.to-top');
  function onScroll() {
    var y = window.scrollY;
    header.classList.toggle('scrolled', y > 30);
    toTop.classList.toggle('show', y > 700);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  toTop.addEventListener('click', function () { window.scrollTo({ top: 0 }); });

  /* ---------- منوی موبایل ---------- */
  var menu = document.getElementById('menu');
  var menuBtn = document.getElementById('menuBtn');
  menuBtn.addEventListener('click', function () {
    var open = menu.classList.toggle('open');
    menuBtn.setAttribute('aria-expanded', open);
  });
  menu.addEventListener('click', function (e) {
    if (e.target.tagName === 'A') { menu.classList.remove('open'); menuBtn.setAttribute('aria-expanded', 'false'); }
  });

  /* ---------- لینک فعال منو ---------- */
  var links = menu.querySelectorAll('a[href^="#"]');
  if ('IntersectionObserver' in window) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle('active', a.getAttribute('href') === '#' + en.target.id); });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    document.querySelectorAll('section[id]').forEach(function (s) { spy.observe(s); });
  }

  /* ---------- جای عکس‌ها: اگر فایل وجود داشت نمایش داده می‌شود ---------- */
  document.querySelectorAll('.media[data-src]').forEach(function (box) {
    var img = new Image();
    img.alt = box.getAttribute('data-alt') || box.getAttribute('data-label') || '';
    img.loading = 'lazy';
    img.decoding = 'async';
    if (box.getAttribute('data-pos')) img.style.objectPosition = box.getAttribute('data-pos');
    // تصویر باید داخل صفحه باشد تا lazy کار کند؛ تا بارگذاری نشده پنهان می‌ماند و جای خالی دیده می‌شود
    img.style.opacity = '0';
    img.onload = function () { img.style.opacity = ''; box.classList.add('has-img'); };
    img.onerror = function () { img.remove(); };
    box.appendChild(img);
    img.src = box.getAttribute('data-src');
  });

  /* ---------- نوار برندها: تکرار برای حرکت بی‌پایان ---------- */
  var track = document.querySelector('.brands-track');
  if (track) {
    Array.prototype.slice.call(track.children).forEach(function (n) {
      var c = n.cloneNode(true);
      c.setAttribute('aria-hidden', 'true');
      track.appendChild(c);
    });
  }

  /* ---------- ظاهر شدن تدریجی و شمارنده‌ها ---------- */
  var fa = new Intl.NumberFormat('fa-IR');
  function count(el) {
    var end = parseInt(el.getAttribute('data-count'), 10) || 0;
    var suffix = el.getAttribute('data-suffix') || '';
    var t0 = null;
    function tick(t) {
      if (!t0) t0 = t;
      var p = Math.min((t - t0) / 1600, 1);
      el.textContent = fa.format(Math.round(end * (1 - Math.pow(1 - p, 3)))) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        en.target.classList.add('in');
        en.target.querySelectorAll('[data-count]').forEach(count);
        io.unobserve(en.target);
      });
    }, { threshold: .15 });
    document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('in'); });
    document.querySelectorAll('[data-count]').forEach(function (el) {
      el.textContent = fa.format(+el.getAttribute('data-count')) + (el.getAttribute('data-suffix') || '');
    });
  }

  /* ---------- سامانه‌های کارکنان: نشانی = همین سرور + پورت هر سامانه ---------- */
  var PORTS = { pichak: 8081, bime: 8082 };
  function portalUrl(name) { return location.protocol + '//' + location.hostname + ':' + PORTS[name] + '/'; }
  function paintPortal() {
    document.querySelectorAll('[data-portal]').forEach(function (a) { a.href = portalUrl(a.getAttribute('data-portal')); });
    document.querySelectorAll('[data-addr]').forEach(function (s) { s.textContent = location.hostname + ':' + PORTS[s.getAttribute('data-addr')]; });
  }
  paintPortal();
  if (window.fetch) fetch('/ports.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
    .then(function (p) {
      if (!p) return;
      ['pichak', 'bime'].forEach(function (k) { if (+p[k]) PORTS[k] = +p[k]; });
      paintPortal();
      // سامانه‌های داخلی (بیمه و حواله) بیرون از شبکه شرکت اصلاً نشان داده نمی‌شوند
      if (p.internal === false) document.querySelectorAll('[data-internal]').forEach(function (el) {
        el.hidden = true; el.parentNode.classList.add('solo');
      });
    }).catch(function () {});
  document.querySelectorAll('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      var url = portalUrl(b.getAttribute('data-copy')), span = b.querySelector('[data-addr]'), old = span.textContent;
      var done = function () { span.textContent = 'کپی شد ✓'; setTimeout(function () { span.textContent = old; }, 1500); };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(done, function () { window.prompt('نشانی را کپی کنید:', url); });
      else window.prompt('نشانی را کپی کنید:', url);
    });
  });

  document.getElementById('year').textContent = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { year: 'numeric' }).format(new Date());
})();
