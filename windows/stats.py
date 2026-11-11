"""آمار بازدید تأمین کالا باختر — فقط روی سرور شرکت (data/stats.db)، بدون کوکی و بدون سرویس خارجی.

رویدادها:
    view     بازدید صفحه        target: site | pichak | app (باز شدن برنامه‌ی نصب‌شده‌ی استعلام چک)
    system   باز شدن سامانه‌ی داخلی  target: bime | ras-chek | tohfe | inventory
    inquiry  استعلام چک          target: registered | not_registered | unknown | error
    section  دیده شدن بخش سایت   target: id بخش (از main.js)
    brand    باز شدن پنجره‌ی برند  target: نام برند
    install  نصب برنامه‌ی استعلام چک

نشانی IP ذخیره نمی‌شود: بازدیدکننده‌ی یکتا = هش (IP + مرورگر + کلید همان روز)؛ کلید هر روز عوض می‌شود،
پس هیچ بازدیدکننده‌ای بین روزها قابل ردیابی نیست.
طراحی و توسعه: شرکت رهوار پیوند داده
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

TEHRAN = timezone(timedelta(hours=3, minutes=30))   # ایران از ۱۴۰۱ ساعت تابستانی ندارد
KEEP_DAYS = 400
BOTS = re.compile(r"bot|crawl|spider|slurp|lighthouse|headless|curl|wget|python|powershell|httpclient|java/|go-http|monitor|preview|facebookexternalhit|whatsapp/|telegrambot", re.I)
MOBILE = re.compile(r"mobi|android|iphone|ipad|ipod", re.I)
KINDS_FROM_PAGE = {"section": 40, "brand": 40, "install": 20}   # رویدادهایی که خود صفحه می‌فرستد → حداکثر طول target
SOURCES = (("google", "گوگل"), ("bing", "بینگ"), ("yandex", "یاندکس"), ("t.me", "تلگرام"), ("telegram", "تلگرام"), ("whatsapp", "واتس‌اپ"),
           ("wa.me", "واتس‌اپ"), ("instagram", "اینستاگرام"), ("eitaa", "ایتا"), ("bale", "بله"), ("rubika", "روبیکا"), ("neshan", "نشان"),
           ("balad", "بلد"))


class Stats:
    def __init__(self, data_dir: Path, log=None):
        self.log = log
        self.path = data_dir / "stats.db"
        key_file = data_dir / "stats.key"
        if not key_file.exists():
            key_file.write_text(secrets.token_hex(32), encoding="ascii")
        self.key = key_file.read_text(encoding="ascii").strip()
        self.lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            ts INTEGER NOT NULL, day TEXT NOT NULL, hour INTEGER NOT NULL, kind TEXT NOT NULL, target TEXT NOT NULL,
            visitor TEXT, device TEXT, source TEXT)""")
        self.db.execute("CREATE INDEX IF NOT EXISTS ev_day ON events(day, kind)")
        cutoff = (datetime.now(TEHRAN) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
        self.db.execute("DELETE FROM events WHERE day < ?", (cutoff,))

    # ------------------------------------------------------------ recording
    @staticmethod
    def is_bot(environ) -> bool:
        return not environ.get("HTTP_USER_AGENT") or bool(BOTS.search(environ["HTTP_USER_AGENT"]))

    @staticmethod
    def _client_ip(environ) -> str:
        # فقط برای شمارش یکتا (نه امنیت): پشت ابرآروان نشانی واقعی در این هدرها می‌آید
        for h in ("HTTP_AR_REAL_IP", "HTTP_X_REAL_IP", "HTTP_X_FORWARDED_FOR"):
            if environ.get(h):
                return environ[h].split(",")[0].strip()
        return environ.get("REMOTE_ADDR", "")

    def _source(self, environ) -> str:
        ref = environ.get("HTTP_REFERER", "")
        host = (urlparse(ref).hostname or "").lower()
        if not host:
            return "مستقیم"
        own = (environ.get("HTTP_HOST") or "").split(":")[0].lower()
        if host == own or host.endswith(".tkbp.ir") or host == "tkbp.ir" or host.endswith("tamintabriz.ir") or re.match(r"^(\d+\.){3}\d+$", host):
            return "داخل سایت"
        for needle, name in SOURCES:
            if needle in host:
                return name
        return host.removeprefix("www.")[:40]

    def record(self, environ, kind: str, target: str, source: bool = False):
        try:
            now = datetime.now(TEHRAN)
            day = now.strftime("%Y-%m-%d")
            ua = environ.get("HTTP_USER_AGENT", "")
            visitor = hashlib.sha256(f"{self.key}|{day}|{self._client_ip(environ)}|{ua}".encode()).hexdigest()[:16]
            row = (int(time.time()), day, now.hour, kind, target[:60], visitor,
                   "mobile" if MOBILE.search(ua) else "desktop", self._source(environ) if source else None)
            with self.lock:
                self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)", row)
        except Exception:   # آمار هرگز نباید سایت را از کار بیندازد
            if self.log:
                self.log.exception("stats record failed")

    def beacon(self, environ, start_response):
        """POST /__s از صفحه: {"k": "section", "t": "brands"}"""
        try:
            size = min(int(environ.get("CONTENT_LENGTH") or 0), 512)
            data = json.loads(environ["wsgi.input"].read(size) or b"{}")
            kind, target = str(data.get("k", "")), str(data.get("t", "")).strip()
            if kind in KINDS_FROM_PAGE and 0 < len(target) <= KINDS_FROM_PAGE[kind] and not self.is_bot(environ):
                self.record(environ, kind, target)
        except (ValueError, KeyError, TypeError):
            pass
        start_response("204 No Content", [("Cache-Control", "no-store")])
        return []

    # ------------------------------------------------------------ reading
    def report(self, days: int) -> dict:
        days = max(1, min(int(days), 365))
        today = datetime.now(TEHRAN).date()
        start = (today - timedelta(days=days - 1)).isoformat()
        prev_start = (today - timedelta(days=2 * days - 1)).isoformat()
        q = lambda sql, *a: self.db.execute(sql, a).fetchall()   # noqa: E731

        def totals(lo, hi):
            r = {}
            for kind, target, n, u in q("""SELECT kind, target, COUNT(*), COUNT(DISTINCT day || visitor) FROM events
                                           WHERE day >= ? AND day < ? GROUP BY kind, target""", lo, hi):
                r.setdefault(kind, {})[target] = [n, u]
            return r
        end = (today + timedelta(days=1)).isoformat()
        cur, prev = totals(start, end), totals(prev_start, start)

        def pick(t, kind, target=None, i=0):
            d = t.get(kind, {})
            return d.get(target, [0, 0])[i] if target else sum(v[i] for v in d.values())

        def kpi(kind, target=None, i=0):
            return {"now": pick(cur, kind, target, i), "prev": pick(prev, kind, target, i)}

        daily = {d: {"site": 0, "visitors": 0, "pichak": 0, "inquiries": 0, "systems": 0}
                 for d in ((today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1))}
        for day, kind, target, n, u in q("""SELECT day, kind, target, COUNT(*), COUNT(DISTINCT visitor) FROM events
                                           WHERE day >= ? AND kind IN ('view','inquiry','system') GROUP BY day, kind, target""", start):
            if day not in daily:
                continue
            if kind == "view" and target == "site":
                daily[day]["site"] += n
                daily[day]["visitors"] += u
            elif kind == "view":
                daily[day]["pichak"] += n
            elif kind == "inquiry":
                daily[day]["inquiries"] += n
            else:
                daily[day]["systems"] += n

        top = lambda kind, extra="": [list(r) for r in q(f"""SELECT target, COUNT(*) c FROM events WHERE day >= ? AND kind = ? {extra}
                                                             GROUP BY target ORDER BY c DESC LIMIT 12""", start, kind)]  # noqa: E731
        devices = dict(q("""SELECT device, COUNT(DISTINCT day || visitor) FROM events
                           WHERE day >= ? AND kind = 'view' AND target = 'site' GROUP BY device""", start))
        sources = [list(r) for r in q("""SELECT source, COUNT(*) c FROM events WHERE day >= ? AND kind = 'view' AND target = 'site'
                                        AND source IS NOT NULL AND source != 'داخل سایت' GROUP BY source ORDER BY c DESC LIMIT 8""", start)]
        hours = [0] * 24
        for h, n in q("SELECT hour, COUNT(*) FROM events WHERE day >= ? AND kind IN ('view','inquiry','system') GROUP BY hour", start):
            hours[h] = n
        return {
            "days": days, "from": start, "to": today.isoformat(),
            "kpi": {
                "site_views": kpi("view", "site"), "site_visitors": kpi("view", "site", 1),
                "pichak_views": {k: kpi("view", "pichak")[k] + kpi("view", "app")[k] for k in ("now", "prev")},
                "inquiries": kpi("inquiry"), "inquiries_ok": {k: kpi("inquiry", "registered")[k] + kpi("inquiry", "not_registered")[k] for k in ("now", "prev")},
                "app_opens": kpi("view", "app"), "installs": kpi("install"), "systems": kpi("system"),
            },
            "daily": [{"day": d, **v} for d, v in daily.items()],
            "devices": devices, "sources": sources, "hours": hours,
            "sections": top("section"), "brands": top("brand"),
            "inquiry_results": dict(q("SELECT target, COUNT(*) FROM events WHERE day >= ? AND kind = 'inquiry' GROUP BY target", start)),
            "systems": top("system"),
        }
