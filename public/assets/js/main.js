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

  /* ---------- پرش به بخش‌ها: بخش‌های پایین صفحه تا دیده نشوند ارتفاع تخمینی دارند (content-visibility)،
     پس بعد از رسیدن، اگر جای بخش عوض شده بود، دوباره دقیق تنظیم می‌شود ---------- */
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    var id = a && a.getAttribute('href').slice(1), target = id && document.getElementById(id);
    if (!target) return;
    e.preventDefault();
    var pad = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0, tries = 0;
    var settle = function () {
      var off = target.getBoundingClientRect().top - pad;
      if (Math.abs(off) > 3 && tries++ < 6) { window.scrollBy(0, off); setTimeout(settle, 120); }
    };
    target.scrollIntoView({ behavior: 'smooth' });
    var done = false, finish = function () { if (!done) { done = true; settle(); } };
    if ('onscrollend' in window) window.addEventListener('scrollend', finish, { once: true });
    setTimeout(finish, 1200);
    if (history.replaceState) history.replaceState(null, '', '#' + id);
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

  // اندازه‌گیری بخش‌های پایین صفحه بعد از اولین نمایش، تا بارگذاری اولیه سریع بماند
  var later = window.requestIdleCallback ? function (f) { requestIdleCallback(f, { timeout: 1500 }); } : function (f) { setTimeout(f, 300); };

  /* ---------- پانورامای انبار: بخش sticky است؛ اسکرول عمودی داخل آن فقط تصویر را به راست می‌برد ---------- */
  var infra = document.querySelector('.infra'), stage = infra && infra.querySelector('.infra-sticky'),
      panoBox = infra && infra.querySelector('.infra-media'), panoImg = panoBox && panoBox.querySelector('img'),
      panoBar = infra && infra.querySelector('.infra-progress span');
  if (panoImg) {
    var room = 0, panoQueued = false;
    var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    var panoLayout = function () {
      var off = reduce || window.innerHeight < 520;   // صفحه‌ی خیلی کوتاه (گوشی افقی): بدون سنجاق
      infra.classList.toggle('static', off);
      if (off) { infra.style.height = ''; room = 0; return; }
      room = Math.max(0, panoImg.offsetWidth - panoBox.offsetWidth);
      // هر پیکسل حرکت افقی ≈ ۱٫۲ پیکسل اسکرول تا حرکت آرام و قابل کنترل باشد
      infra.style.height = (stage.offsetHeight + room * 1.2) + 'px';
      panoMove();
    };
    var panoMove = function () {
      panoQueued = false;
      if (!room) return;
      var total = infra.offsetHeight - stage.offsetHeight;
      var prog = Math.min(1, Math.max(0, -infra.getBoundingClientRect().top / total));
      panoImg.style.transform = 'translate3d(' + (-prog * room).toFixed(1) + 'px,0,0)';
      if (panoBar) panoBar.style.setProperty('--p', prog.toFixed(4));
      infra.classList.toggle('moved', prog > 0.04);
    };
    window.addEventListener('scroll', function () { if (!panoQueued) { panoQueued = true; requestAnimationFrame(panoMove); } }, { passive: true });
    window.addEventListener('resize', panoLayout);
    later(function () { if (panoImg.complete) panoLayout(); else panoImg.addEventListener('load', panoLayout); });
  }

  /* ---------- برندها: فیلتر دسته‌بندی، ردیف‌های تمام‌عرض و پنجره‌ی برند ---------- */
  var grid = document.getElementById('brandGrid');
  if (grid) {
    var items = Array.prototype.slice.call(grid.querySelectorAll('.bs-item')), filter = 'همه', visible = items;
    var ratio = function (el) { return parseFloat(el.style.getPropertyValue('--r')) || 1.6; };
    // کارت‌ها به ردیف‌هایی تقسیم می‌شوند که جمع نسبت‌هایشان نزدیک هم است؛ هر ردیف دقیقاً تمام عرض را پر می‌کند
    var split = function (list, target) {
      if (!list.length) return [];
      var total = list.reduce(function (t, el) { return t + ratio(el); }, 0);
      var n = Math.max(1, Math.round(total / target)), rows = [], cur = [], sum = 0;
      list.forEach(function (el, i) {
        cur.push(el); sum += ratio(el);
        var rowsLeft = n - rows.length - 1;
        if (rowsLeft > 0 && (sum >= total / n - 0.6 || list.length - i - 1 === rowsLeft)) { rows.push(cur); cur = []; sum = 0; }
      });
      if (cur.length) rows.push(cur);
      return rows;
    };
    var layout = function () {
      visible = items.filter(function (el) { return filter === 'همه' || el.getAttribute('data-cat') === filter; });
      // برندهای اصلی (data-featured) اول و در ردیف‌های کم‌جمعیت‌تر، یعنی کارت‌های بزرگ‌تر
      var big = visible.filter(function (el) { return el.hasAttribute('data-featured'); });
      var rest = visible.filter(function (el) { return !el.hasAttribute('data-featured'); });
      visible = big.concat(rest);
      var phone = grid.clientWidth < 600;
      // گوشی: هر برند اصلی یک ردیف کامل
      var rows = (phone ? big.map(function (el) { return [el]; }) : split(big, 4.8)).concat(split(rest, phone ? 2.6 : 7));
      grid.textContent = '';
      rows.forEach(function (r) {
        var row = document.createElement('div'); row.className = 'bs-row';
        r.forEach(function (el) { row.appendChild(el); });
        grid.appendChild(row);
      });
      grid.classList.add('rows');
    };
    later(layout);
    var rsz; window.addEventListener('resize', function () { clearTimeout(rsz); rsz = setTimeout(layout, 150); });
    var setFilter = function (f) {
      filter = f;
      document.querySelectorAll('.bs-tabs button').forEach(function (b) { var on = b.getAttribute('data-filter') === f; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on); });
      layout();
    };
    document.querySelectorAll('.bs-tabs button').forEach(function (btn) {
      btn.addEventListener('click', function () { setFilter(btn.getAttribute('data-filter')); });
    });
    // «برندهای این گروه» در کارت‌های حوزه فعالیت: فیلتر همان دسته را روشن می‌کند
    document.querySelectorAll('[data-brand-filter]').forEach(function (a) {
      a.addEventListener('click', function () { setFilter(a.getAttribute('data-brand-filter')); });
    });

    var pop = document.getElementById('brandPop'), at = 0;
    var show = function (i) {
      at = (i + visible.length) % visible.length;
      var el = visible[at], img = el.querySelector('img');
      document.getElementById('bpImg').src = img.getAttribute('data-full') || img.currentSrc || img.src;
      document.getElementById('bpImg').alt = img.alt;
      document.getElementById('bpName').textContent = el.querySelector('b').textContent;
      document.getElementById('bpCo').textContent = el.querySelector('small').textContent;
      document.getElementById('bpTag').textContent = el.getAttribute('data-cat');
      document.getElementById('bpCount').textContent = new Intl.NumberFormat('fa-IR').format(at + 1) + ' از ' + new Intl.NumberFormat('fa-IR').format(visible.length);
    };
    if (pop && pop.showModal) {
      grid.addEventListener('click', function (e) {
        var el = e.target.closest('.bs-item'); if (!el) return;
        show(visible.indexOf(el)); pop.showModal();
      });
      pop.querySelector('.bp-close').addEventListener('click', function () { pop.close(); });
      pop.querySelector('.bp-prev').addEventListener('click', function () { show(at - 1); });
      pop.querySelector('.bp-next').addEventListener('click', function () { show(at + 1); });
      pop.addEventListener('click', function (e) { if (e.target === pop) pop.close(); });   // کلیک بیرون پنجره
      pop.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowRight') show(at + 1); else if (e.key === 'ArrowLeft') show(at - 1);   // هم‌جهت با دکمه‌ها: راست = بعدی
      });
      var tx = null;   // ورق زدن با انگشت
      pop.addEventListener('touchstart', function (e) { tx = e.touches[0].clientX; }, { passive: true });
      pop.addEventListener('touchend', function (e) {
        if (tx === null) return; var dx = e.changedTouches[0].clientX - tx; tx = null;
        if (Math.abs(dx) > 50) show(dx > 0 ? at + 1 : at - 1);
      });
    }
  }

  /* ---------- گالری: عکس کامل در پنجره (Esc، دکمه‌ی بستن، کلیک بیرون، قبلی/بعدی، کشیدن انگشت) ---------- */
  var gal = Array.prototype.slice.call(document.querySelectorAll('.g-open')), gp = document.getElementById('galPop');
  if (gal.length && gp && gp.showModal) {
    var gAt = 0, num = new Intl.NumberFormat('fa-IR');
    var gShow = function (i) {
      gAt = (i + gal.length) % gal.length;
      var btn = gal[gAt], im = btn.querySelector('img');
      document.getElementById('gpImg').src = btn.getAttribute('data-full');
      document.getElementById('gpImg').alt = im.alt;
      document.getElementById('gpCap').textContent = btn.parentNode.querySelector('figcaption').textContent;
      document.getElementById('gpCount').textContent = num.format(gAt + 1) + ' از ' + num.format(gal.length);
    };
    gal.forEach(function (btn, i) { btn.addEventListener('click', function () { gShow(i); gp.showModal(); }); });
    gp.querySelector('.bp-close').addEventListener('click', function () { gp.close(); });
    gp.querySelector('.bp-prev').addEventListener('click', function () { gShow(gAt - 1); });
    gp.querySelector('.bp-next').addEventListener('click', function () { gShow(gAt + 1); });
    gp.addEventListener('click', function (e) { if (e.target === gp) gp.close(); });
    gp.addEventListener('keydown', function (e) { if (e.key === 'ArrowRight') gShow(gAt + 1); else if (e.key === 'ArrowLeft') gShow(gAt - 1); });
    var gx = null;
    gp.addEventListener('touchstart', function (e) { gx = e.touches[0].clientX; }, { passive: true });
    gp.addEventListener('touchend', function (e) {
      if (gx === null) return; var dx = e.changedTouches[0].clientX - gx; gx = null;
      if (Math.abs(dx) > 50) gShow(dx > 0 ? gAt + 1 : gAt - 1);
    });
  }

  /* ---------- شعبه‌ها: زبانه‌ی تبریز / اردبیل؛ نشانی، تلفن و نقشه‌ی همان شعبه ---------- */
  var brTabs = Array.prototype.slice.call(document.querySelectorAll('.branch-tabs [role="tab"]')), brMap = document.getElementById('branchMap');
  var pickBranch = function (tab, focus) {
    brTabs.forEach(function (t) {
      var on = t === tab;
      t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
    });
    if (brMap && brMap.getAttribute('src') !== tab.getAttribute('data-map')) {
      brMap.src = tab.getAttribute('data-map');
      brMap.title = 'موقعیت شعبه‌ی ' + tab.firstChild.textContent.trim() + ' تأمین کالا باختر روی نقشه نشان';
    }
    if (focus) tab.focus();
  };
  brTabs.forEach(function (t, i) {
    t.addEventListener('click', function () { pickBranch(t); });
    t.addEventListener('keydown', function (e) {   // جهت‌نماها بین زبانه‌ها (راست‌به‌چپ)
      var d = e.key === 'ArrowLeft' ? 1 : e.key === 'ArrowRight' ? -1 : 0;
      if (d) { e.preventDefault(); pickBranch(brTabs[(i + d + brTabs.length) % brTabs.length], true); }
    });
  });

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
  // data-path: سامانه‌ای که زیر همان پورت است (مثلاً /ras-chek/ روی پورت سامانه‌های داخلی)
  function portalAddr(name, path) { return (onDomain && HOSTS[name] ? HOSTS[name] : location.hostname + ':' + PORTS[name]) + (path && path !== '/' ? path.replace(/\/$/, '') : ''); }
  function portalUrl(name, path) { return location.protocol + '//' + portalAddr(name) + (path || '/'); }
  function paintPortal() {
    document.querySelectorAll('[data-portal]').forEach(function (a) { a.href = portalUrl(a.getAttribute('data-portal'), a.getAttribute('data-path')); });
    document.querySelectorAll('[data-addr]').forEach(function (s) { s.textContent = portalAddr(s.getAttribute('data-addr'), s.getAttribute('data-path')); });
  }
  paintPortal();
  // سامانه‌های داخلی (بیمه و حواله، رأس‌گیری، گزارش تحفه، کنترل موجودی) فقط وقتی سایت با IP خصوصی (داخل شرکت) باز شده نشان داده می‌شوند؛
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
      var url = portalUrl(b.getAttribute('data-copy'), b.getAttribute('data-path')), span = b.querySelector('[data-addr]'), old = span.textContent;
      var done = function () {
        if (span.hidden) { b.classList.add('copied'); setTimeout(function () { b.classList.remove('copied'); }, 1500); return; }
        span.textContent = 'کپی شد ✓'; setTimeout(function () { span.textContent = old; }, 1500);
      };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(done, function () { window.prompt('نشانی را کپی کنید:', url); });
      else window.prompt('نشانی را کپی کنید:', url);
    });
  });

  document.getElementById('year').textContent = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { year: 'numeric' }).format(new Date());
})();
