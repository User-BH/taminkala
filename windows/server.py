"""تأمین کالا باختر — سرور یکپارچه برای ویندوز (و لینوکس)
طراحی و توسعه: شرکت رهوار پیوند داده

یک برنامه، سه پورت:
    site   (پیش‌فرض 80)   سایت معرفی شرکت          ← public/
    pichak (پیش‌فرض 8081) استعلام وضعیت ثبتی چک    ← pichak/ (Flask)
    bime   (پیش‌فرض 8082) سامانه بیمه و حواله      ← bime/

هیچ مسیری از سایت اصلی به سامانه‌ها نمی‌رسد (مثلاً /pichak صفحه ۴۰۴ می‌دهد)؛
سایت نشانی سامانه‌ها را از /ports.json می‌خواند و با پورت خودشان لینک می‌دهد.

تنظیمات: data/config.json (اگر نباشد با مقادیر پیش‌فرض ساخته می‌شود)
اجرا:    python server.py            (روی ویندوز install.bat این را خودکار اجرا می‌کند)
"""
from __future__ import annotations

import ipaddress
import json
import logging
import logging.handlers
import gzip
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
SITE_DIR, BIME_DIR, PICHAK_DIR = ROOT / "public", ROOT / "bime", ROOT / "pichak"
DATA_DIR, LOG_DIR = ROOT / "data", ROOT / "logs"
CONFIG_FILE = DATA_DIR / "config.json"
# bime_allow: فقط این شبکه‌ها به سامانه بیمه و حواله دسترسی دارند (شبکه داخلی شرکت و خود سرور)
PRIVATE_NETS = ["127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "::1/128"]
# pichak_host: subdomain that serves the cheque inquiry on the site port,
# so it works behind a CDN such as ArvanCloud with HTTPS (CDNs usually pass only ports 80/443)
DEFAULTS = {"site_port": 80, "pichak_port": 8081, "bime_port": 8082, "pichak_ocr": True, "threads": 8, "bime_allow": PRIVATE_NETS,
            "pichak_host": "check.tkbp.ir"}

mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("application/xml", ".xml")
COMPRESSIBLE = ("text/", "application/javascript", "application/json", "application/manifest+json", "application/xml", "image/svg+xml")
_GZ_CACHE: dict = {}   # (path, mtime) -> gzipped bytes


def _gzipped(file: Path) -> bytes:
    st = file.stat()
    key = (str(file), st.st_mtime_ns)
    if key not in _GZ_CACHE:
        if len(_GZ_CACHE) > 200:
            _GZ_CACHE.clear()
        _GZ_CACHE[key] = gzip.compress(file.read_bytes(), 6)
    return _GZ_CACHE[key]


def load_config() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig")))
    else:
        CONFIG_FILE.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
    for k in ("site_port", "pichak_port", "bime_port"):
        cfg[k] = int(cfg[k])
    if len({cfg["site_port"], cfg["pichak_port"], cfg["bime_port"]}) != 3:
        raise SystemExit("config.json: the three ports must be different")
    host = cfg.get("pichak_host") or ""
    if isinstance(host, list):
        host = next((h for h in host if str(h).strip()), "")
    cfg["_pichak_hosts"] = [str(host).strip().lower().rstrip(".")] if str(host).strip() else []
    cfg["pichak_host"] = cfg["_pichak_hosts"][0] if cfg["_pichak_hosts"] else ""
    cfg["_bime_nets"] = [ipaddress.ip_network(n, strict=False) for n in cfg.get("bime_allow") or PRIVATE_NETS]
    return cfg


def _host(environ) -> str:
    return (environ.get("HTTP_HOST") or "").split(":")[0].strip().lower().rstrip(".")


def client_allowed(environ, nets) -> bool:
    """IP واقعی اتصال (REMOTE_ADDR)؛ هدر X-Forwarded-For عمداً نادیده گرفته می‌شود چون قابل جعل است."""
    try:
        ip = ipaddress.ip_address(environ.get("REMOTE_ADDR", ""))
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in n for n in nets)


def internal_host(environ) -> bool:
    """Was the page requested by an internal name (private IP, localhost, a computer name)?
    Second line of defence for bime: if the router rewrites outside visitors to its own LAN address
    (masquerade on forwarded traffic), REMOTE_ADDR alone would look internal; a public IP or a domain
    in the Host header still gives it away."""
    host = (environ.get("HTTP_HOST") or environ.get("SERVER_NAME") or "").strip().lower()
    host = host[1:host.index("]")] if host.startswith("[") and "]" in host else host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return "." not in host or host.endswith((".local", ".lan", ".internal"))


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(LOG_DIR / "server.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler(sys.stderr)] if sys.stderr else [handler])
    return logging.getLogger("taminkala")


# ---------------------------------------------------------------- static files
def _page(start_response, status, name, fallback):
    page = SITE_DIR / name
    body = page.read_bytes() if page.exists() else fallback
    start_response(status, [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")])
    return [body]


def _not_found(start_response):
    return _page(start_response, "404 Not Found", "404.html", b"404 Not Found")


def _internal_only(start_response):
    return _page(start_response, "403 Forbidden", "internal-only.html", b"403 Forbidden")


def _resolve(root: Path, url_path: str) -> Path | None:
    """Safe path inside root (no ../, no hidden files); directories map to index.html."""
    parts = [p for p in url_path.split("/") if p]
    if any(p.startswith(".") or "\\" in p or ":" in p for p in parts):
        return None
    target = root.joinpath(*parts) if parts else root
    try:
        target = target.resolve()
        target.relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    if target.is_dir():
        target = target / "index.html"
    return target if target.is_file() else None


def static_app(root: Path, extra_roots: dict[str, Path] | None = None, extra_files: dict | None = None):
    extra_roots = extra_roots or {}
    extra_files = extra_files or {}

    def app(environ, start_response):
        if environ["REQUEST_METHOD"] not in ("GET", "HEAD"):
            start_response("405 Method Not Allowed", [("Content-Type", "text/plain"), ("Allow", "GET, HEAD")])
            return [b"Method Not Allowed"]
        path = environ.get("PATH_INFO", "/")
        if path in extra_files:
            body, ctype = extra_files[path]()
            start_response("200 OK", [("Content-Type", ctype), ("Cache-Control", "no-store"), ("Content-Length", str(len(body)))])
            return [body] if environ["REQUEST_METHOD"] == "GET" else []
        base = root
        for prefix, other in extra_roots.items():
            if path.startswith(prefix):
                base, path = other, path[len(prefix) - 1:]
                break
        file = _resolve(base, path)
        if file is None:
            return _not_found(start_response)
        ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        # فونت هرگز عوض نمی‌شود؛ بقیه (CSS/JS/عکس‌ها با همان نام) با هر به‌روزرسانی ممکن است عوض شوند:
        # مرورگر نگه می‌دارد ولی هر بار با ETag می‌پرسد و اگر تغییری نبود فقط پاسخ کوتاه 304 می‌گیرد
        st = file.stat()
        etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
        cache = "public, max-age=31536000, immutable" if file.suffix == ".woff2" else "no-cache"
        headers = [("Content-Type", ctype), ("Cache-Control", cache), ("ETag", etag), ("X-Content-Type-Options", "nosniff"), ("Vary", "Accept-Encoding")]
        if environ.get("HTTP_IF_NONE_MATCH") == etag:
            start_response("304 Not Modified", headers[1:])
            return []
        if ctype.startswith(COMPRESSIBLE) and "gzip" in environ.get("HTTP_ACCEPT_ENCODING", ""):
            body = _gzipped(file)
            start_response("200 OK", headers + [("Content-Encoding", "gzip"), ("Content-Length", str(len(body)))])
            return [] if environ["REQUEST_METHOD"] == "HEAD" else [body]
        start_response("200 OK", headers + [("Content-Length", str(file.stat().st_size))])
        if environ["REQUEST_METHOD"] == "HEAD":
            return []
        return environ["wsgi.file_wrapper"](file.open("rb"), 65536) if "wsgi.file_wrapper" in environ else [file.read_bytes()]

    return app


# ---------------------------------------------------------------- pichak
def pichak_app(cfg, log, stats):
    os.environ["PICHAK_OCR"] = "1" if cfg.get("pichak_ocr", True) else "0"
    os.environ.setdefault("PICHAK_DUMP_DIR", str(LOG_DIR / "cbi"))   # unrecognized bank answers, for support
    sys.path.insert(0, str(PICHAK_DIR))
    try:
        from app import app as flask_app   # pichak/app.py
    except Exception:
        log.exception("Pichak could not start; its port will show an error page")

        def broken(environ, start_response):
            body = "سامانه استعلام چک در حال حاضر در دسترس نیست. فایل logs/server.log را بررسی کنید.".encode("utf-8")
            start_response("503 Service Unavailable", [("Content-Type", "text/plain; charset=utf-8")])
            return [body]
        return broken
    assets = static_app(SITE_DIR)

    def _counted_inquiry(environ, start_response):
        """نتیجه‌ی استعلام برای آمار: ثبت‌شده / ثبت‌نشده / نامشخص / خطا (پاسخ بدون تغییر به کاربر می‌رسد)"""
        captured = {}

        def sr(status, headers, exc_info=None):
            captured["status"] = status
            return start_response(status, headers, exc_info) if exc_info else start_response(status, headers)
        body = b"".join(flask_app(environ, sr))
        result = "error"
        if captured.get("status", "").startswith("200"):
            try:
                reg = json.loads(body).get("is_registered")
                result = "registered" if reg is True else "not_registered" if reg is False else "unknown"
            except ValueError:
                pass
        if not stats.is_bot(environ):
            stats.record(environ, "inquiry", result)
        return [body]

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/")
        if path.startswith("/assets/") or path == "/404.html":
            return assets(environ, start_response)
        if path == "/__s" and environ["REQUEST_METHOD"] == "POST":
            return stats.beacon(environ, start_response)
        if path == "/api/inquire" and environ["REQUEST_METHOD"] == "POST":
            return _counted_inquiry(environ, start_response)
        if path.startswith("/api/"):
            return flask_app(environ, start_response)
        if path == "/" and environ["REQUEST_METHOD"] == "GET" and not stats.is_bot(environ):
            # start_url برنامه‌ی نصب‌شده ?source=app دارد
            stats.record(environ, "view", "app" if "source=app" in environ.get("QUERY_STRING", "") else "pichak", source=True)
        # صفحه‌های پیچک؛ اگر برنامه ۴۰۴ داد، ۴۰۴ قالب تأمین کالا نشان داده شود
        captured = {}

        def sr(status, headers, exc_info=None):
            captured["status"], captured["headers"] = status, headers
            return lambda data: None
        body = flask_app(environ, sr)
        if captured.get("status", "").startswith("404"):
            if hasattr(body, "close"):
                body.close()
            return _not_found(start_response)
        start_response(captured["status"], captured["headers"])
        return body

    return app


# ---------------------------------------------------------------- dispatch
INTERNAL_SYSTEMS = {"/": "bime", "/index.html": "bime", "/ras-chek/": "ras-chek", "/tohfe/": "tohfe", "/inventory/": "inventory"}


def build(cfg, log):
    site = static_app(SITE_DIR)
    from stats import Stats   # windows/stats.py، کنار همین فایل
    stats = Stats(DATA_DIR, log)

    def site_app(environ, start_response):
        path = environ.get("PATH_INFO", "/")
        if path == "/__s" and environ["REQUEST_METHOD"] == "POST":
            return stats.beacon(environ, start_response)
        if path in ("/", "/index.html") and environ["REQUEST_METHOD"] == "GET" and not stats.is_bot(environ):
            stats.record(environ, "view", "site", source=True)
        if environ.get("PATH_INFO") == "/ports.json":   # «internal» برای نمایش یا قفل کارت بیمه در سایت
            # زیردامنه‌ی استعلام چک هم‌دامنه با همان نشانی‌ای که سایت با آن باز شده (tkbp.ir → check.tkbp.ir)
            asked = _host(environ).removeprefix("www.")
            ph = next((h for h in cfg["_pichak_hosts"] if h.split(".", 1)[-1] == asked), cfg["pichak_host"])
            body = json.dumps({"pichak": cfg["pichak_port"], "bime": cfg["bime_port"], "pichak_host": ph,
                               "internal": client_allowed(environ, cfg["_bime_nets"])}).encode()
            start_response("200 OK", [("Content-Type", "application/json"), ("Cache-Control", "no-store"), ("Content-Length", str(len(body)))])
            return [body]
        return site(environ, start_response)

    bime = static_app(BIME_DIR, extra_roots={"/assets/": SITE_DIR / "assets"})
    site_assets = static_app(SITE_DIR)

    def bime_app(environ, start_response):
        if not (client_allowed(environ, cfg["_bime_nets"]) and internal_host(environ)):
            if environ.get("PATH_INFO", "").startswith("/assets/"):   # فقط فایل‌های ظاهری صفحه پیام
                return site_assets(environ, start_response)
            log.warning("bime blocked for %s (host %s)", environ.get("REMOTE_ADDR"), environ.get("HTTP_HOST"))
            return _internal_only(start_response)
        path = environ.get("PATH_INFO", "/")
        if path == "/stats/api.json":   # داشبورد آمار (فقط شبکه‌ی داخلی)
            qs = parse_qs(environ.get("QUERY_STRING", ""))
            try:
                days = int(qs.get("days", ["30"])[0])
            except ValueError:
                days = 30
            body = json.dumps(stats.report(days), ensure_ascii=False).encode()
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8"), ("Cache-Control", "no-store"), ("Content-Length", str(len(body)))])
            return [body]
        system = INTERNAL_SYSTEMS.get(path) or INTERNAL_SYSTEMS.get(path + "/")
        if system and environ["REQUEST_METHOD"] == "GET" and not stats.is_bot(environ):
            stats.record(environ, "system", system)
        return bime(environ, start_response)

    pichak = pichak_app(cfg, log, stats)
    apps = {
        cfg["site_port"]: site_app,
        cfg["pichak_port"]: pichak,
        cfg["bime_port"]: bime_app,
    }

    def dispatch(environ, start_response):
        if _host(environ) in cfg["_pichak_hosts"]:
            return pichak(environ, start_response)
        app = apps.get(int(environ.get("SERVER_PORT") or 0))
        if app is None:
            return _not_found(start_response)
        return app(environ, start_response)

    return dispatch


def main():
    log = setup_logging()
    cfg = load_config()
    from waitress import serve
    # فقط IPv4: روی سرورهایی که IPv6 خاموش است «*» باعث خطای شروع می‌شود
    listen = " ".join(f"0.0.0.0:{cfg[k]}" for k in ("site_port", "pichak_port", "bime_port"))
    log.info("starting: site=%s pichak=%s bime=%s (bime allowed from %s)%s", cfg["site_port"], cfg["pichak_port"], cfg["bime_port"],
             ", ".join(map(str, cfg["_bime_nets"])), f"; pichak also at {', '.join(cfg['_pichak_hosts'])}" if cfg["_pichak_hosts"] else "")
    # clear_untrusted_proxy_headers=False: هدرهای X-Forwarded-For/Ar-Real-IP ابرآروان فقط برای شمارش بازدیدکننده‌ی یکتا
    # خوانده می‌شوند؛ دسترسی سامانه‌های داخلی همچنان فقط با نشانی واقعی اتصال (REMOTE_ADDR) سنجیده می‌شود
    serve(build(cfg, log), listen=listen, threads=int(cfg.get("threads", 8)), ident="TaminKala",
          channel_timeout=130,   # استعلام بانک مرکزی ممکن است طول بکشد
          clear_untrusted_proxy_headers=False)


if __name__ == "__main__":
    main()
