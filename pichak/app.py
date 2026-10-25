"""Small, single-worker CBI Sayad check web application.

This is an *experimental* integration with a public ASP.NET page, not an
approved CBI API. Always verify actual CBI HTML/network responses in Iran.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from captcha_inline import extract_inline_captcha_source
from flask import Flask, jsonify, request, send_from_directory

HERE = Path(__file__).resolve().parent
CBI_URL = "https://cbi.ir/EstelamPichak/22036.aspx"
FIXED_CUSTOMER_TYPE = "2"  # حقوقی
FIXED_ID_CODE = "14005736802"  # شرکت تامین کالا باختر
SESSION_TTL = 300
SESSION_MAX = 150
MAX_CAPTCHA_BYTES = 1_200_000
OCR_ENABLED = os.getenv("PICHAK_OCR", "0").lower() in {"1", "yes", "true"}

app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
logging.basicConfig(level=logging.INFO)


@dataclass
class StoredSession:
    handler: "CBISessionHandler"
    created: float


SESSIONS: OrderedDict[str, StoredSession] = OrderedDict()
SESSIONS_LOCK = threading.Lock()


def only_digits(value):
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def validate_input(data):
    sayad = only_digits(data.get("sayad_id", "")).strip()
    due = only_digits(data.get("due_date", "")).strip()
    amount = only_digits(data.get("amount", "")).replace(",", "").replace("٬", "").strip()
    captcha = only_digits(data.get("captcha_answer", "")).strip()
    if not re.fullmatch(r"\d{16}", sayad):
        raise ValueError("شناسه صیادی باید دقیقاً ۱۶ رقم باشد.")
    match = re.fullmatch(r"(1[34]\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])", due)
    if not match:
        raise ValueError("تاریخ سررسید باید به صورت ۱۴۰۵/۰۹/۰۳ باشد.")
    if not re.fullmatch(r"\d{1,16}", amount) or int(amount) <= 0:
        raise ValueError("مبلغ ریالی چک نامعتبر است.")
    if not re.fullmatch(r"\d{1,6}", captcha):
        raise ValueError("پاسخ کپچا باید عددی باشد.")
    return sayad, due, amount, captcha


def solve_simple_math_image(image_data_uri):
    """Produce a conservative, user-verifiable OCR suggestion or None."""
    if not OCR_ENABLED:
        return None
    try:
        from captcha_math_ocr import solve
        return solve(image_data_uri)
    except Exception as exc:
        app.logger.info("OCR unavailable or undecidable: %s", type(exc).__name__)
        return None


class CBISessionHandler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.7",
            "Referer": CBI_URL,
        })
        self.viewstate = ""
        self.viewstate_generator = ""
        self.event_validation = ""
        self.baseline = frozenset()   # text of the empty form, to tell the bank's answer apart

    @staticmethod
    def _first_captcha_image(soup):
        # CBI has used the misspelling "cpatcha" as an image id in some templates.
        needle = re.compile(r"capt|cpatch|security.?code|verify.?code", re.I)
        for img in soup.find_all("img"):
            hint = " ".join(str(img.get(k, "")) for k in ("id", "name", "class", "alt", "title", "src", "data-src"))
            if needle.search(hint):
                return img
        return None

    @staticmethod
    def _same_cbi_host(url):
        host = (urlparse(url).hostname or "").lower()
        return host == "cbi.ir" or host.endswith(".cbi.ir")

    def _captcha_as_data_uri(self, src, page_url):
        src = (src or "").strip()
        if src.lower().startswith("data:image/"):
            if ";base64," not in src.lower():
                raise ValueError("CBI_CAPTCHA_UNSUPPORTED_DATA_URI")
            prefix, encoded = src.split(",", 1)
            if not re.fullmatch(r"data:image/(?:png|jpeg|jpg|gif|webp);base64", prefix, re.I):
                raise ValueError("CBI_CAPTCHA_UNSUPPORTED_IMAGE_FORMAT")
            if len(encoded) > MAX_CAPTCHA_BYTES * 4 // 3 + 100:
                raise ValueError("CBI_CAPTCHA_IMAGE_TOO_LARGE")
            try:
                raw = base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise ValueError("CBI_CAPTCHA_INVALID_BASE64") from exc
            if not raw or len(raw) > MAX_CAPTCHA_BYTES:
                raise ValueError("CBI_CAPTCHA_IMAGE_TOO_LARGE")
            return src
        target = urljoin(page_url, src)
        if not src or urlparse(target).scheme != "https" or not self._same_cbi_host(target):
            raise ValueError("CBI_CAPTCHA_UNKNOWN_SOURCE")
        image = self.session.get(target, timeout=(7, 20), allow_redirects=False,
                                 headers={"Referer": page_url, "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.8"})
        image.raise_for_status()
        if image.status_code in (301, 302, 303, 307, 308):
            raise ValueError("CBI_CAPTCHA_IMAGE_REDIRECT")
        binary = image.content
        if not binary or len(binary) > MAX_CAPTCHA_BYTES:
            raise ValueError("CBI_CAPTCHA_IMAGE_TOO_LARGE")
        content_type = image.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        # Verify binary signatures; prevents accidentally returning an HTML access-denied page.
        if binary.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif binary.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif binary.startswith((b"GIF87a", b"GIF89a")):
            mime = "image/gif"
        elif binary.startswith(b"RIFF") and binary[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            raise ValueError("CBI_CAPTCHA_NOT_IMAGE:" + content_type[:40])
        return f"data:{mime};base64,{base64.b64encode(binary).decode('ascii')}"

    def fetch_captcha(self):
        try:
            response = self.session.get(CBI_URL, timeout=(7, 25))
            response.raise_for_status()
        except requests.Timeout as exc:
            raise ValueError("CBI_TIMEOUT") from exc
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "UNKNOWN"
            raise ValueError(f"CBI_HTTP_{code}") from exc
        except requests.RequestException as exc:
            raise ValueError("CBI_CONNECTION_ERROR") from exc
        if not self._same_cbi_host(response.url):
            raise ValueError("CBI_REDIRECTED_OUTSIDE_OFFICIAL_SITE")
        soup = BeautifulSoup(response.text, "html.parser")
        self.baseline = frozenset(page_texts(response.text))
        for key, field in (("__VIEWSTATE", "viewstate"), ("__VIEWSTATEGENERATOR", "viewstate_generator"), ("__EVENTVALIDATION", "event_validation")):
            item = soup.find("input", id=key) or soup.find("input", attrs={"name": key})
            setattr(self, field, item.get("value", "") if item else "")
        if not self.viewstate:
            raise ValueError("CBI_NO_VIEWSTATE")
        captcha = self._first_captcha_image(soup)
        if captcha is None:
            raise ValueError("CBI_NO_CAPTCHA_IMAGE")
        # CBI's initial <img> may have an empty src. The page includes a
        # literal data:image/...;base64,... in an inline JavaScript call to
        # getElementById(captcha_id).setAttribute("src", data_uri).
        # Extract that literal instead of executing JavaScript or sending
        # extra requests. Keep the exact HTTP session for the inquiry.
        src = captcha.get("src") or captcha.get("data-src") or ""
        if not src:
            src = extract_inline_captcha_source(soup)
        if not src:
            raise ValueError("CBI_CAPTCHA_INLINE_NOT_FOUND")
        return self._captcha_as_data_uri(src, response.url)

    def submit_inquiry(self, sayad_id, due_date, amount, captcha_answer):
        payload = {
            "ctl00$ucBody$ucContent$ctl00$ScriptManager1": "ctl00$ucBody$ucContent$ctl00$UpdatePanel1|ctl00$ucBody$ucContent$ctl00$estelamBtn",
            "ctl00$ucHeader$txtQuickSearch": "",
            "ctl00$ucBody$ucContent$ctl00$txtSayadId": sayad_id,
            "ctl00$ucBody$ucContent$ctl00$txtdueDate": due_date,
            "ctl00$ucBody$ucContent$ctl00$ddlCustomerType": FIXED_CUSTOMER_TYPE,
            "ctl00$ucBody$ucContent$ctl00$txtIdCode": FIXED_ID_CODE,
            "ctl00$ucBody$ucContent$ctl00$txtAmount": f"{int(amount):,}",
            "ctl00$ucBody$ucContent$ctl00$txtCaptchaInput": captcha_answer,
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": self.viewstate,
            "__VIEWSTATEGENERATOR": self.viewstate_generator,
            "__VIEWSTATEENCRYPTED": "",
            "__ASYNCPOST": "true",
            "ctl00$ucBody$ucContent$ctl00$estelamBtn": "استعلام",
        }
        if self.event_validation:
            payload["__EVENTVALIDATION"] = self.event_validation
        response = self.session.post(CBI_URL, data=payload, headers={
            "X-MicrosoftAjax": "Delta=true",
            "X-Requested-With": "XMLHttpRequest",
            "Cache-Control": "no-cache",
        }, timeout=(7, 30))
        response.raise_for_status()
        return parse_cbi_response(response.text, self.baseline)

    def close(self):
        self.session.close()


_FA_NORM = str.maketrans({"ي": "ی", "ك": "ک", "\u200c": " ", "\u200f": "", "\u200e": "", "\xa0": " "})
_FA_LITERAL = re.compile(r"""(['"])((?:(?!\1)[^\\\n]|\\.)*?[\u0600-\u06FF](?:(?!\1)[^\\\n]|\\.)*?)\1""")
NOT_REGISTERED = ("ثبت نشده", "ثبت نگردیده", "ثبت نشد")
UNCERTAIN = ("کد امنیتی", "کد تصویر", "کپچا", "captcha", "منقضی", "مجدد", "خطا", "نامعتبر", "معتبر نمی", "اشتباه",
             "صحیح نیست", "صحیح نمی", "مطابقت ندارد", "مطابقت نداشت", "مغایرت", "یافت نشد", "وجود ندارد")
REGISTERED = ("ثبت شده", "ثبت شد", "ثبت گردیده", "ثبت گردید")
DUMP_DIR = Path(os.getenv("PICHAK_DUMP_DIR") or HERE / "logs" / "cbi")
DUMP_KEEP = 30


def _norm(text):
    return re.sub(r"\s+", " ", str(text).translate(_FA_NORM)).strip()


def _delta_parts(raw):
    """ASP.NET AJAX partial response: «length|type|id|content|» repeated. None if raw is not one."""
    parts, i = [], 0
    while i < len(raw):
        j = raw.find("|", i)
        k = raw.find("|", j + 1) if j >= 0 else -1
        m = raw.find("|", k + 1) if k >= 0 else -1
        if m < 0 or not raw[i:j].isdigit():
            return None
        n = int(raw[i:j])
        parts.append((raw[j + 1:k], raw[k + 1:m], raw[m + 1:m + 1 + n]))
        i = m + 1 + n + 1
    return parts or None


_HIDDEN = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)


def _visible_soup(html):
    """Parsed fragment without scripts, styles, dropdowns and hidden elements (e.g. inactive validators)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "select", "noscript", "template"]):
        tag.decompose()
    for tag in soup.find_all(style=_HIDDEN):
        tag.decompose()
    for tag in soup.find_all(attrs={"hidden": True}):
        tag.decompose()
    return soup


def _script_literals(html):
    soup = BeautifulSoup(html, "html.parser")
    return [_norm(m.group(2)) for tag in soup.find_all("script") for m in _FA_LITERAL.finditer(tag.get_text())]


def page_texts(html):
    """Visible text pieces of an HTML fragment and the Persian string literals of its scripts (alert/swal...)."""
    return [_norm(t) for t in _visible_soup(html).stripped_strings] + _script_literals(html)


def _take_holders(soup, baseline):
    """Holder rows (type, national/company id, name); the tables they are in are removed from ``soup``."""
    holders = []
    for table in soup.find_all("table"):
        found = []
        for row in table.find_all("tr"):
            cols = [_norm(td.get_text(" ", strip=True)) for td in row.find_all("td")]
            # a holder row carries a national/company id; layout rows of the form never do
            if len(cols) >= 3 and re.fullmatch(r"\d{8,12}", only_digits(cols[1])) and not all(c in baseline for c in cols):
                found.append({"customer_type": cols[0], "id_code": cols[1], "name": cols[2]})
        if found:
            holders += found
            table.decompose()
    return holders


def _sentence(text):
    """Tidy one line of bank text: spacing after Persian comma, ':' at the end becomes '.'."""
    text = re.sub(r"\s*([،,])\s*", r"\1 ", text).strip()
    text = re.sub(r"\s*[:：]\s*$", "", text)
    return text if re.search(r"[.!؟?]$", text) else text + "."


def _dump(raw, reason):
    """Keep unrecognized bank answers on this server (never sent anywhere) so the parser can be improved."""
    try:
        DUMP_DIR.mkdir(parents=True, exist_ok=True)
        cleaned = re.sub(r'(<input[^>]+name="__(?:VIEWSTATE|EVENTVALIDATION)[^"]*"[^>]*value=")[^"]*', r"\1", raw)
        cleaned = re.sub(r"(\d+\|hiddenField\|__(?:VIEWSTATE|EVENTVALIDATION)\|)[^|]*", r"\1", cleaned)
        name = DUMP_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}-{reason}.txt"
        name.write_text(cleaned, encoding="utf-8")
        for old in sorted(DUMP_DIR.glob("*.txt"))[:-DUMP_KEEP]:
            old.unlink()
        app.logger.warning("Unrecognized CBI answer saved to %s", name)
    except OSError:
        app.logger.exception("Could not save the CBI answer")


def parse_cbi_response(raw, baseline=frozenset()):
    """Classify the bank's answer; fail closed.

    The bank page isn't a stable public API, so element ids are not relied on: the answer is the
    visible text that appears in the response but was not on the empty form (``baseline``).
    A check is reported registered/unregistered only on explicit wording; anything else is shown
    as the bank's own message with is_registered None. Errors are never read as "unregistered".
    Result: message (the status sentence), holders, note (the bank's other remarks).
    """
    parts = _delta_parts(raw)
    if parts is None:
        fragments, scripts = [raw], []
    else:
        for typ, _pid, content in parts:
            if typ == "error":
                return {"success": False, "is_registered": None, "holders": [], "note": "",
                        "message": "بانک خطا برگرداند: " + _norm(content)[:300]}
            if typ == "pageRedirect":
                return {"success": False, "is_registered": None, "holders": [], "note": "",
                        "message": "بانک صفحه را به نشانی دیگری فرستاد؛ نتیجه را در سامانه رسمی بررسی کنید."}
        fragments = [c for t, _i, c in parts if t == "updatePanel"]
        scripts = [c for t, _i, c in parts if t.startswith("scriptBlock") or t.startswith("ScriptContent")
                   or t == "scriptStartupBlock" or t == "onSubmit"]
    holders, texts = [], []
    for fragment in fragments:
        soup = _visible_soup(fragment)
        holders += _take_holders(soup, baseline)
        texts += [_norm(t) for t in soup.stripped_strings] + _script_literals(fragment)
    texts += [_norm(m.group(2)) for js in scripts for m in _FA_LITERAL.finditer(js)]
    seen, answer = set(baseline), []
    for t in texts:
        if len(t) > 1 and t not in seen:
            seen.add(t)
            answer.append(t)
    low = " ".join(answer).lower()
    status = next((t for t in answer if any(w in t for w in REGISTERED + NOT_REGISTERED)), "")
    note = " ".join(_sentence(t) for t in answer if t != status)[:600]
    registered = any(w in status for w in REGISTERED) and not any(w in status for w in NOT_REGISTERED)

    def result(ok, reg, message, rows=(), with_note=True):
        return {"success": ok, "is_registered": reg, "message": message, "holders": list(rows), "note": note if with_note else ""}

    if registered and holders:   # explicit wording plus the bank's holder table: unambiguous
        # form-validation leftovers ("... معتبر نمی باشد") contradict the holder table; keep only the bank's remarks
        note = " ".join(_sentence(t) for t in answer if t != status and not any(w in t.lower() for w in UNCERTAIN))[:600]
        return result(True, True, _sentence(status), holders)
    if any(w in status for w in NOT_REGISTERED) and not any(w in low for w in UNCERTAIN):
        return result(True, False, _sentence(status))
    if any(w in low for w in UNCERTAIN):
        return result(False, None, "پیام بانک: " + " ".join(_sentence(t) for t in answer)[:500], with_note=False)
    if registered or holders:
        return result(True, True, _sentence(status) if status else "ثبت چک توسط بانک مرکزی تأیید شد.", holders)
    _dump(raw, "unknown")
    if answer:
        return result(False, None, "پیام بانک: " + " ".join(_sentence(t) for t in answer)[:500]
                      + "\nنتیجه خودکار تشخیص داده نشد؛ متن بالا پاسخ خود بانک است.", with_note=False)
    return result(False, None, "پاسخ بانک متن قابل نمایشی نداشت؛ این به معنی ثبت‌نشدن چک نیست. در سامانه رسمی بررسی کنید.",
                  with_note=False)


def save_session(handler):
    now = time.monotonic()
    key = uuid.uuid4().hex
    with SESSIONS_LOCK:
        expired = [k for k, entry in SESSIONS.items() if now - entry.created > SESSION_TTL]
        for k in expired:
            SESSIONS.pop(k).handler.close()
        while len(SESSIONS) >= SESSION_MAX:
            SESSIONS.popitem(last=False)[1].handler.close()
        SESSIONS[key] = StoredSession(handler, now)
    return key


def take_session(key):
    with SESSIONS_LOCK:
        item = SESSIONS.pop(key, None)
    if not item:
        return None
    if time.monotonic() - item.created > SESSION_TTL:
        item.handler.close()
        return None
    return item.handler


@app.get("/")
def home():
    return send_from_directory(HERE, "index.html", mimetype="text/html")


@app.get("/logo.png")
def logo():
    if not (HERE / "logo.png").is_file():
        return "Logo is not installed", 404
    return send_from_directory(HERE, "logo.png")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "pichak", "cbi_tested": False})


@app.get("/api/captcha")
def get_captcha():
    handler = CBISessionHandler()
    try:
        src = handler.fetch_captcha()
        ocr_result = solve_simple_math_image(src)
        key = save_session(handler)
        return jsonify({"success": True, "session_key": key, "captcha_src": src,
                        "auto_answer": ocr_result["answer"] if ocr_result else None,
                        "ocr_expression": ocr_result["expression"] if ocr_result else None,
                        "auto_suggested": ocr_result is not None})
    except Exception as exc:
        handler.close()
        error_code = str(exc) if isinstance(exc, ValueError) and str(exc).startswith("CBI_") else "CBI_UNEXPECTED_FAILURE"
        app.logger.warning("CBI captcha unavailable: %s", error_code)
        return jsonify({"success": False, "error_code": error_code,
                        "message": "دریافت کپچا انجام نشد. کد خطا را در راهنمای عیب‌یابی بررسی کنید."}), 502


@app.post("/api/inquire")
def inquire():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "بدنه درخواست JSON معتبر نیست.", "is_registered": None}), 400
    try:
        args = validate_input(data)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc), "is_registered": None}), 400
    session_key = data.get("session_key")
    if not isinstance(session_key, str) or not re.fullmatch(r"[a-f0-9]{32}", session_key):
        return jsonify({"success": False, "message": "نشست کپچا معتبر نیست.", "is_registered": None}), 400
    handler = take_session(session_key)
    if handler is None:
        return jsonify({"success": False, "message": "نشست کپچا منقضی یا استفاده شده است.", "is_registered": None}), 400
    try:
        return jsonify(handler.submit_inquiry(*args))
    except requests.RequestException:
        app.logger.warning("CBI inquiry network failure")
        return jsonify({"success": False, "is_registered": None,
                        "message": "اتصال به بانک مرکزی قطع شد یا پاسخ به‌موقع دریافت نشد."}), 502
    except Exception:
        app.logger.exception("Unexpected CBI response")
        return jsonify({"success": False, "is_registered": None,
                        "message": "خطا در پردازش پاسخ بانک؛ نتیجه استعلام نامشخص است."}), 502
    finally:
        handler.close()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8088, debug=False)
