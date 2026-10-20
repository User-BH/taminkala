#!/usr/bin/env bash
# ==========================================================
#  نصب OCR جدید کپچای پیچک (یا برگشت به نسخه قبل)
#  طراحی و توسعه: شرکت رهوار پیوند داده
#
#    sudo taminkala pichak-ocr             ← نصب/به‌روزرسانی
#    sudo taminkala pichak-ocr rollback    ← برگشت به OCR قبلی
#
#  فقط دو فایل OCR در /opt/pichak عوض می‌شود؛ بقیه برنامه دست نمی‌خورد.
#  قبل از نصب تست می‌شود و اگر سرویس بعد از نصب سالم بالا نیاید،
#  خودکار نسخه قبلی برگردانده می‌شود.
# ==========================================================
set -Eeuo pipefail

PICHAK_DIR=${PICHAK_DIR:-/opt/pichak}
PY=${PICHAK_PY:-$PICHAK_DIR/venv/bin/python}
SERVICE=${PICHAK_SERVICE:-pichak.service}
UPSTREAM=${PICHAK_UPSTREAM:-127.0.0.1:8088}
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../pichak-ocr" && pwd)
FILES=(captcha_math_ocr.py captcha_templates.py)
BACKUPS=$PICHAK_DIR/backups-ocr

G=$'\e[32m'; R=$'\e[31m'; Y=$'\e[33m'; B=$'\e[36m'; N=$'\e[0m'
ok()   { echo "${G}✔${N} $*"; }
say()  { echo "${B}▸${N} $*"; }
warn() { echo "${Y}⚠${N} $*"; }
die()  { echo "${R}✘ $*${N}" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "با sudo اجرا کنید."
[[ -d $PICHAK_DIR ]] || die "پوشه پیچک ($PICHAK_DIR) پیدا نشد."
[[ -x $PY ]] || die "پایتون venv پیچک ($PY) پیدا نشد."

owner=$(stat -c '%U:%G' "$PICHAK_DIR/app.py")

restart_and_check() {
  systemctl restart "$SERVICE"
  for _ in $(seq 1 20); do
    sleep 1
    [[ $(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://$UPSTREAM/api/health") == 200 ]] && return 0
  done
  return 1
}

restore() {  # restore <backup-dir>
  for f in "${FILES[@]}"; do
    if [[ -f $1/$f ]]; then cp -p "$1/$f" "$PICHAK_DIR/$f"; else rm -f "$PICHAK_DIR/$f"; fi
  done
}

if [[ ${1:-} == rollback ]]; then
  last=$(ls -1d "$BACKUPS"/* 2>/dev/null | tail -1)
  [[ -n $last ]] || die "پشتیبانی از OCR قبلی پیدا نشد."
  say "برگشت به OCR ذخیره‌شده در $last …"
  restore "$last"
  restart_and_check && ok "OCR قبلی برگردانده شد و پیچک سالم است." || die "پیچک بعد از برگشت پاسخ نمی‌دهد: journalctl -u $SERVICE -n 50"
  exit 0
fi

live_test() {
  say "آزمایش با ۵ کپچای زنده…"
  local hits=0 r expr i
  for i in 1 2 3 4 5; do
    r=$(curl -s -m 40 "http://$UPSTREAM/api/captcha" || true)
    expr=$("$PY" - "$r" <<'PYEOF'
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    print("خطا"); sys.exit()
print(d.get("ocr_expression") or ("بدون پیشنهاد" if d.get("success") else "خطا: " + str(d.get("error_code"))))
PYEOF
)
    [[ $expr =~ ^[0-9]+\+[0-9]+$ ]] && hits=$((hits+1))
    echo "    کپچای $i: $expr"
    sleep 2
  done
  ok "OCR برای $hits از ۵ کپچا پاسخ پیشنهاد داد."
  echo "  اگر نتیجه مناسب نبود:  sudo taminkala pichak-ocr rollback"
}

# ۱) تست با همان پایتونی که پیچک با آن اجرا می‌شود
say "تست OCR جدید روی نمونه‌های واقعی…"
(cd "$SRC" && "$PY" -B -m unittest -q test_captcha_ocr) || die "تست‌ها رد شدند؛ چیزی نصب نشد."
ok "تست‌ها موفق بودند."

# ۲) پشتیبان و نصب (اگر همین نسخه از قبل نصب است، پشتیبان تکراری ساخته نمی‌شود
#    تا rollback همیشه به OCR واقعاً قبلی برگردد)
same=1
for f in "${FILES[@]}"; do cmp -s "$SRC/$f" "$PICHAK_DIR/$f" || same=0; done
if (( same )); then
  ok "همین نسخه OCR از قبل نصب است؛ فقط آزمایش زنده انجام می‌شود."
  live_test
  exit 0
fi
stamp=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUPS/$stamp"
for f in "${FILES[@]}"; do [[ -f $PICHAK_DIR/$f ]] && cp -p "$PICHAK_DIR/$f" "$BACKUPS/$stamp/"; done
for f in "${FILES[@]}"; do
  install -m 644 -o "${owner%%:*}" -g "${owner##*:}" "$SRC/$f" "$PICHAK_DIR/$f"
done
ok "فایل‌ها نصب شدند (پشتیبان: $BACKUPS/$stamp)."

# ۳) ری‌استارت و بررسی سلامت؛ در صورت خطا برگشت خودکار
say "ری‌استارت $SERVICE …"
if ! restart_and_check; then
  warn "پیچک سالم بالا نیامد؛ برگشت به نسخه قبل…"
  restore "$BACKUPS/$stamp"
  restart_and_check || true
  die "نصب لغو شد و نسخه قبلی برگردانده شد. لاگ: journalctl -u $SERVICE -n 50"
fi
ok "پیچک سالم است."

# ۴) آزمایش زنده با چند کپچای بانک مرکزی
live_test
