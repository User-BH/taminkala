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

  /* ---------- پانورامای انبار: با اسکرول خیلی آرام از راست به چپ حرکت می‌کند ---------- */
  var pano = document.querySelector('.infra-media'), panoImg = pano && pano.querySelector('img');
  if (panoImg && !(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) {
    var panoQueued = false;
    var panoMove = function () {
      panoQueued = false;
      var r = pano.getBoundingClientRect(), vh = window.innerHeight;
      if (r.bottom < 0 || r.top > vh) return;
      var prog = Math.min(1, Math.max(0, (vh - r.top) / (vh + r.height)));   // ۰ وقتی وارد می‌شود، ۱ وقتی خارج می‌شود
      var room = panoImg.offsetWidth - pano.offsetWidth;
      panoImg.style.transform = 'translate3d(' + (-prog * room).toFixed(1) + 'px,0,0)';
    };
    var panoQueue = function () { if (!panoQueued) { panoQueued = true; requestAnimationFrame(panoMove); } };
    window.addEventListener('scroll', panoQueue, { passive: true });
    window.addEventListener('resize', panoQueue);
    panoImg.addEventListener('load', panoQueue);
    panoQueue();
  }

  /* ---------- برندها: ردیف خودکار حرکت می‌کند و دستی هم ورق می‌خورد ----------
     کارت‌ها دو بار تکرار می‌شوند؛ وقتی موقعیت از طول یک دور گذشت، بی‌صدا به ابتدا برمی‌گردد. */
  var mq = document.querySelector('.brand-marquee'), track = mq && mq.querySelector('.brand-track');
  if (track) {
    var originals = Array.prototype.slice.call(track.children);
    for (var k = 0; k < 2; k++) originals.forEach(function (card) {
      var copy = card.cloneNode(true);
      copy.setAttribute('aria-hidden', 'true');
      copy.querySelectorAll('img').forEach(function (img) { img.alt = ''; });
      track.appendChild(copy);
    });
    var still = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    var SPEED = 36, pos = 0, last = 0, hover = false, holdUntil = 0, drag = null;
    var loop = function () { return track.children[originals.length].offsetLeft - track.children[0].offsetLeft; };
    var step = function () { return track.children[0].offsetWidth + parseFloat(getComputedStyle(track).columnGap || 22); };
    var hold = function (ms) { holdUntil = performance.now() + (ms || 2500); };
    var wrap = function () {
      var L = loop(), x = mq.scrollLeft;
      if (x >= L) mq.scrollLeft = x - L; else if (x <= 0) mq.scrollLeft = x + L;
    };
    mq.scrollLeft = loop();   // از وسط شروع می‌شود تا دو طرف جا برای ورق زدن باشد
    pos = mq.scrollLeft;
    (function tick(t) {
      var dt = last ? Math.min(t - last, 64) / 1000 : 0; last = t;
      if (!still && !hover && !drag && t > holdUntil) {
        pos += SPEED * dt;
        var L = loop();
        if (pos >= 2 * L) pos -= L;
        mq.scrollLeft = pos;
      } else {
        if (!drag && t > holdUntil - 2000) wrap();
        pos = mq.scrollLeft;
      }
      requestAnimationFrame(tick);
    })(0);
    mq.addEventListener('mouseenter', function () { hover = true; });
    mq.addEventListener('mouseleave', function () { hover = false; });
    mq.addEventListener('touchstart', function () { hold(4000); }, { passive: true });
    mq.addEventListener('touchmove', function () { hold(4000); }, { passive: true });
    mq.addEventListener('wheel', function () { hold(3000); }, { passive: true });
    mq.addEventListener('focusin', function () { hold(6000); });
    mq.addEventListener('pointerdown', function (e) {   // کشیدن با ماوس
      if (e.pointerType !== 'mouse' || e.button !== 0) return;
      drag = { x: e.clientX, left: mq.scrollLeft };
      mq.classList.add('dragging');
    });
    window.addEventListener('pointermove', function (e) { if (drag) mq.scrollLeft = drag.left - (e.clientX - drag.x); });
    window.addEventListener('pointerup', function () { if (drag) { drag = null; mq.classList.remove('dragging'); hold(2500); } });
    mq.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); go(e.key === 'ArrowRight' ? -1 : 1); }
    });
    function go(dir) {   // dir=1: برند بعدی (به چپ)، dir=-1: برند قبلی
      wrap(); hold(3500);
      mq.scrollBy({ left: dir * step(), behavior: still ? 'auto' : 'smooth' });
    }
    var prev = document.querySelector('.bm-prev'), next = document.querySelector('.bm-next');
    if (prev) prev.addEventListener('click', function () { go(-1); });
    if (next) next.addEventListener('click', function () { go(1); });
  }

  /* ---------- وضعیت باز/بسته بودن شرکت (به وقت تهران: شنبه تا پنجشنبه ۷ تا ۱۷) ---------- */
  var openEl = document.getElementById('openState');
  if (openEl) try {
    var parts = {};
    new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Tehran', weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' })
      .formatToParts(new Date()).forEach(function (x) { parts[x.type] = x.value; });
    var mins = (+parts.hour % 24) * 60 + +parts.minute;
    var isOpen = parts.weekday !== 'Fri' && mins >= 7 * 60 && mins < 17 * 60;
    openEl.textContent = isOpen ? 'الان باز است' : 'الان بسته است';
    openEl.classList.toggle('is-open', isOpen);
    openEl.hidden = false;
  } catch (e) {}

  /* ---------- سامانه‌های کارکنان: نشانی = همین سرور + پورت هر سامانه ---------- */
  var PORTS = { pichak: 8081, bime: 8082 }, HOSTS = {};
  // روی دامنه (پشت ابرآروان) استعلام چک از زیردامنه‌ی خودش باز می‌شود؛ با IP از پورت خودش
  var onDomain = !/^(\d+\.){3}\d+$|^\[|^localhost$/.test(location.hostname);
  var privateHost = /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.)|^localhost$/.test(location.hostname);
  function portalAddr(name) { return onDomain && HOSTS[name] ? HOSTS[name] : location.hostname + ':' + PORTS[name]; }
  function portalUrl(name) { return location.protocol + '//' + portalAddr(name) + '/'; }
  function paintPortal() {
    document.querySelectorAll('[data-portal]').forEach(function (a) { a.href = portalUrl(a.getAttribute('data-portal')); });
    document.querySelectorAll('[data-addr]').forEach(function (s) { s.textContent = portalAddr(s.getAttribute('data-addr')); });
  }
  paintPortal();
  // سامانه‌ی بیمه و حواله فقط وقتی سایت با IP خصوصی (داخل شرکت) باز شده نشان داده می‌شود؛
  // با IP عمومی یا دامنه کارت آن پنهان است (پورت آن هم از بیرون بسته است)
  if (!privateHost) document.querySelectorAll('[data-internal]').forEach(function (el) {
    el.hidden = true; el.parentNode.classList.add('solo');
  });
  if (window.fetch) fetch('/ports.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
    .then(function (p) {
      if (!p) return;
      ['pichak', 'bime'].forEach(function (k) { if (+p[k]) PORTS[k] = +p[k]; });
      if (p.pichak_host) HOSTS.pichak = p.pichak_host;
      paintPortal();

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
