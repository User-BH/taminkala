/* سامانه‌های داخلی: لینک «سامانه‌ها» به بخش سامانه‌های سایت شرکت روی همین سرور */
(function () {
  var site = location.protocol + '//' + location.hostname + '/#portal';
  document.querySelectorAll('.sys-back').forEach(function (a) { a.href = site; });
})();
