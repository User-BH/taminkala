/* تأمین کالا باختر — اسکریپت‌های سایت | طراحی و توسعه: شرکت رهوار پیوند داده */
(function () {
  'use strict';
  var root = document.documentElement;
  var KEY = 'tkb-theme';
  var mq = window.matchMedia('(prefers-color-scheme: dark)');
  var LABELS = { auto: 'خودکار (مطابق دستگاه)', light: 'حالت روشن', dark: 'حالت تاریک' };

  function store(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function read() { try { return localStorage.getItem(KEY) || 'auto'; } catch (e) { return 'auto'; } }

  /* ---------- تم: خودکار ← روشن ← تاریک ---------- */
  function applyTheme(pref) {
    root.setAttribute('data-theme-pref', pref);
    if (pref === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', pref);
    var dark = pref === 'dark' || (pref === 'auto' && mq.matches);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', dark ? '#15100e' : '#991522');
    var btn = document.getElementById('themeBtn');
    if (btn) {
      btn.setAttribute('aria-label', 'تغییر تم — ' + LABELS[pref]);
      btn.querySelector('.t-label').textContent = LABELS[pref];
    }
  }
  applyTheme(read());
  document.getElementById('themeBtn').addEventListener('click', function () {
    var order = ['auto', 'light', 'dark'];
    var next = order[(order.indexOf(read()) + 1) % order.length];
    store(next);
    applyTheme(next);
  });
  mq.addEventListener && mq.addEventListener('change', function () { applyTheme(read()); });

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
    img.onload = function () { box.appendChild(img); box.classList.add('has-img'); };
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

  document.getElementById('year').textContent = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { year: 'numeric' }).format(new Date());
})();
