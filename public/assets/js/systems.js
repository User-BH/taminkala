/* سامانه‌های داخلی: لینک «سامانه‌ها» به بخش سامانه‌های سایت شرکت روی همین سرور */
(function () {
  var site = location.protocol + '//' + location.hostname + '/#portal';
  var bimeHeader = document.querySelector('body.sys-bime .header');
  if (bimeHeader && !bimeHeader.querySelector('.sys-back')) {
    var tools = document.createElement('div');
    var tag = bimeHeader.querySelector('.top-tag');
    tools.className = 'sys-tools';
    if (tag) tools.appendChild(tag);
    tools.insertAdjacentHTML('beforeend', '<a class="sys-back" href="/" title="بازگشت به فهرست سامانه‌ها"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg><span>سامانه‌ها</span></a>');
    bimeHeader.appendChild(tools);
  }
  document.querySelectorAll('.sys-back').forEach(function (a) { a.href = site; });
})();
