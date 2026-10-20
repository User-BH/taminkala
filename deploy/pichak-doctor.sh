#!/usr/bin/env bash
# ==========================================================
#  پیچک — عیب‌یابی OCR و پورت‌ها + جمع‌آوری نمونه کپچا
#  طراحی و توسعه: شرکت رهوار پیوند داده
#
#  اجرا:   sudo bash /opt/taminkala/deploy/pichak-doctor.sh
#  خروجی: یک فایل pichak-doctor-*.tar.gz که باید برای تیم فنی ارسال شود.
#
#  این اسکریپت هیچ تغییری روی سرور نمی‌دهد (فقط خواندن).
#  اطلاعات مالی، کوکی یا رمز چاپ/ذخیره نمی‌شود؛ فقط تصویر کپچاها
#  (که اطلاعات حساسی ندارند) و خروجی خام OCR ذخیره می‌شود.
# ==========================================================
set -uo pipefail

PICHAK_DIR=${PICHAK_DIR:-/opt/pichak}
PY=${PICHAK_PY:-$PICHAK_DIR/venv/bin/python}
SAMPLES=${SAMPLES:-15}
OUT=/tmp/pichak-doctor-$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT/captchas"
REPORT=$OUT/report.txt

[[ $EUID -eq 0 ]] || { echo "با sudo اجرا کنید:  sudo bash $0"; exit 1; }
[[ -d $PICHAK_DIR ]] || { echo "پوشه $PICHAK_DIR پیدا نشد. مسیر را با PICHAK_DIR=... مشخص کنید."; exit 1; }
[[ -x $PY ]] || { echo "پایتون venv در $PY پیدا نشد. با PICHAK_PY=... مشخص کنید."; exit 1; }

sec() { printf '\n===== %s =====\n' "$*"; }
exec > >(tee "$REPORT") 2>&1
echo "Pichak doctor — $(date '+%Y-%m-%d %H:%M')  host=$(hostname)"

# ---------------------------------------------------------- پورت‌ها
sec "1) LISTENING PORTS (80, 443, 2083, 8081, 8082, 8088)"
for p in 80 443 2083 8081 8082 8088; do
  ss -Hltnp "sport = :$p" 2>/dev/null | while read -r line; do
    pid=$(grep -o 'pid=[0-9]*' <<<"$line" | head -1 | cut -d= -f2)
    addr=$(awk '{print $4}' <<<"$line")
    cmd=$( [[ -n $pid ]] && ps -o args= -p "$pid" 2>/dev/null | cut -c1-160 )
    echo "port $p  addr=$addr  pid=${pid:-?}  cmd=${cmd:-?}"
  done
done
echo "(any port not listed above is free)"

sec "2) NGINX FILES MENTIONING 2083 / 8088 / pichak"
grep -rnE "2083|8088|pichak" /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null \
  | grep -vE "^\s*#" | sed -E 's/(ssl_certificate[_a-z]*\s+).*/\1<path hidden>/' || echo "(none)"

sec "3) SYSTEMD UNITS FOR PICHAK"
if [[ -d /run/systemd/system ]]; then
  for u in $(systemctl list-unit-files --no-legend '*pichak*' 2>/dev/null | awk '{print $1}'); do
    echo "--- $u  active=$(systemctl is-active "$u")  enabled=$(systemctl is-enabled "$u" 2>/dev/null)"
    systemctl cat "$u" 2>/dev/null | grep -E "^(ExecStart|EnvironmentFile|Environment=PICHAK|WorkingDirectory|User)="
  done
  grep -rlE "pichak|8088|2083" /etc/systemd/system/*.service 2>/dev/null | sed 's/^/unit file: /'
fi
echo "--- other pichak/gunicorn processes:"
ps -eo pid,args | grep -E "gunicorn|app\.py|pichak" | grep -v -E "grep|pichak-doctor" | cut -c1-180

sec "4) PICHAK SETTINGS (only PICHAK_ variables)"
for f in "$PICHAK_DIR"/pichak.env "$PICHAK_DIR"/.env /etc/pichak*.env; do
  [[ -f $f ]] && { echo "file: $f"; grep -E "^PICHAK_(OCR|BIND)=" "$f"; }
done
for pid in $(pgrep -f "gunicorn|app\.py" 2>/dev/null); do
  e=$(tr '\0' '\n' < /proc/$pid/environ 2>/dev/null | grep -E "^PICHAK_(OCR|BIND)=" | tr '\n' ' ')
  [[ -n $e ]] && echo "running pid $pid env: $e"
done

sec "5) OCR ENGINE"
if command -v tesseract >/dev/null; then
  tesseract --version 2>&1 | head -1
else
  echo "TESSERACT_MISSING  ← برنامه tesseract نصب نیست (علت اصلی کار نکردن OCR)"
fi
"$PY" - <<'EOF'
import importlib
for m in ("pytesseract", "PIL", "requests", "bs4", "flask"):
    try:
        mod = importlib.import_module(m)
        print(f"python {m}: OK {getattr(mod, '__version__', '')}")
    except Exception as e:
        print(f"python {m}: MISSING ({type(e).__name__})")
try:
    import pytesseract
    print("pytesseract sees tesseract:", pytesseract.get_tesseract_version())
except Exception as e:
    print("pytesseract -> tesseract: FAIL", type(e).__name__)
EOF

sec "6) LIVE CAPTCHA SAMPLES ($SAMPLES) + RAW OCR"
cd "$PICHAK_DIR" && PICHAK_OCR=1 "$PY" - "$OUT/captchas" "$SAMPLES" <<'EOF'
import base64, json, sys, time, traceback
out, n = sys.argv[1], int(sys.argv[2])
sys.path.insert(0, ".")
try:
    import app as pichak
    import captcha_math_ocr as ocr
except Exception as e:
    print("IMPORT_FAIL", type(e).__name__, e); sys.exit(0)

ok = suggested = 0
for i in range(1, n + 1):
    h = pichak.CBISessionHandler()
    try:
        src = h.fetch_captcha()
    except Exception as e:
        print(f"#{i:02d} FETCH_FAIL {type(e).__name__}: {str(e)[:80]}")
        h.close(); time.sleep(3); continue
    h.close()
    ok += 1
    mime, b64 = src.split(";base64,", 1)
    ext = mime.split("/")[-1].replace("jpeg", "jpg")
    name = f"captcha-{i:02d}.{ext}"
    open(f"{out}/{name}", "wb").write(base64.b64decode(b64))
    raw = []
    def engine(img, config=""):
        import pytesseract
        t = pytesseract.image_to_string(img, config=config)
        raw.append({"psm": config.split()[1], "text": t.strip()})
        return t
    try:
        res = ocr.solve(src, ocr_engine=engine)
        err = None
    except Exception as e:
        res, err = None, f"{type(e).__name__}: {e}"
    if res: suggested += 1
    rec = {"file": name, "result": res, "error": err, "raw": raw}
    open(f"{out}/{name}.json", "w").write(json.dumps(rec, ensure_ascii=False, indent=1))
    reads = sorted({r["text"] for r in raw})
    print(f"#{i:02d} {name}  result={res and res['expression']+'='+res['answer']}  err={err}  reads={reads[:6]}")
    time.sleep(2)
print(f"\nSUMMARY fetched={ok}/{n} ocr_suggested={suggested}/{ok}")
EOF

sec "7) RECENT PICHAK LOG LINES (OCR / CBI)"
if [[ -d /run/systemd/system ]]; then
  for u in $(systemctl list-unit-files --no-legend '*pichak*' 2>/dev/null | awk '{print $1}'); do
    journalctl -u "$u" -n 300 --no-pager 2>/dev/null | grep -iE "ocr|captcha|tesseract|error|warn" | tail -25
  done
fi

tar -C /tmp -czf "$OUT.tar.gz" "$(basename "$OUT")"
echo
echo "✔ گزارش آماده شد:  $OUT.tar.gz"
echo "  این فایل را برای بررسی ارسال کنید (مثلاً: scp root@SERVER:$OUT.tar.gz .)"
