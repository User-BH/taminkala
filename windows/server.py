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

import json
import logging
import logging.handlers
import mimetypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE_DIR, BIME_DIR, PICHAK_DIR = ROOT / "public", ROOT / "bime", ROOT / "pichak"
DATA_DIR, LOG_DIR = ROOT / "data", ROOT / "logs"
CONFIG_FILE = DATA_DIR / "config.json"
DEFAULTS = {"site_port": 80, "pichak_port": 8081, "bime_port": 8082, "pichak_ocr": True, "threads": 8}

mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/javascript", ".js")


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
    return cfg


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(LOG_DIR / "server.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler(sys.stderr)] if sys.stderr else [handler])
    return logging.getLogger("taminkala")


# ---------------------------------------------------------------- static files
def _not_found(start_response):
    page = SITE_DIR / "404.html"
    body = page.read_bytes() if page.exists() else b"404 Not Found"
    start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))])
    return [body]


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
        cache = "no-cache" if file.suffix == ".html" else "public, max-age=604800"
        headers = [("Content-Type", ctype), ("Content-Length", str(file.stat().st_size)), ("Cache-Control", cache),
                   ("X-Content-Type-Options", "nosniff")]
        start_response("200 OK", headers)
        if environ["REQUEST_METHOD"] == "HEAD":
            return []
        return environ["wsgi.file_wrapper"](file.open("rb"), 65536) if "wsgi.file_wrapper" in environ else [file.read_bytes()]

    return app


# ---------------------------------------------------------------- pichak
def pichak_app(cfg, log):
    os.environ["PICHAK_OCR"] = "1" if cfg.get("pichak_ocr", True) else "0"
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

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/")
        if path.startswith("/assets/") or path == "/404.html":
            return assets(environ, start_response)
        if path.startswith("/api/"):
            return flask_app(environ, start_response)
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
def build(cfg, log):
    ports_json = lambda: (json.dumps({"pichak": cfg["pichak_port"], "bime": cfg["bime_port"]}).encode(), "application/json")
    apps = {
        cfg["site_port"]: static_app(SITE_DIR, extra_files={"/ports.json": ports_json}),
        cfg["pichak_port"]: pichak_app(cfg, log),
        cfg["bime_port"]: static_app(BIME_DIR, extra_roots={"/assets/": SITE_DIR / "assets"}),
    }

    def dispatch(environ, start_response):
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
    log.info("starting: site=%s pichak=%s bime=%s", cfg["site_port"], cfg["pichak_port"], cfg["bime_port"])
    serve(build(cfg, log), listen=listen, threads=int(cfg.get("threads", 8)), ident="TaminKala",
          channel_timeout=130)   # استعلام بانک مرکزی ممکن است طول بکشد


if __name__ == "__main__":
    main()
