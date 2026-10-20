#!/usr/bin/env bash
# ==========================================================
#  تأمین کالا باختر — نصب و به‌روزرسانی سایت از مخزن گیت
#  طراحی و توسعه: شرکت رهوار پیوند داده
#
#  اولین بار (روی سرور اوبونتو/دبیان):
#     curl -fsSL <آدرس خام همین فایل> -o taminkala.sh && sudo bash taminkala.sh install
#     یا اگر مخزن را دارید:  sudo bash deploy/taminkala.sh install
#
#  دفعات بعد کافی است بنویسید:
#     sudo taminkala            ← منوی ساده
#     sudo taminkala update     ← به‌روزرسانی مستقیم
#
#  دستورها: install | update | status | rollback | settings | help
#
#  نکته: سامانه پیچک (/opt/pichak) با این اسکریپت تغییر نمی‌کند؛
#  فقط از طریق Nginx روی پورت خودش در دسترس قرار می‌گیرد.
# ==========================================================
set -Eeuo pipefail

# اجرا از روی یک کپی موقت: به‌روزرسانی خود این فایل را عوض می‌کند و bash
# اسکریپت در حال اجرا را خط‌به‌خط می‌خواند؛ پس نباید از فایل اصلی اجرا شود.
if [[ -z ${TKB_RUNNING_COPY:-} ]]; then
  _tmp=$(mktemp /tmp/taminkala.XXXXXX.sh)
  cp "$(readlink -f "$0")" "$_tmp"
  TKB_SRC_DIR=$(dirname "$(readlink -f "$0")") TKB_RUNNING_COPY=$_tmp exec bash "$_tmp" "$@"
fi
trap 'rm -f "$TKB_RUNNING_COPY"' EXIT

CONF_DIR=/etc/taminkala
CONF_FILE=$CONF_DIR/taminkala.env
BACKUP_DIR=$CONF_DIR/backups
NGINX_SITE=/etc/nginx/sites-available/taminkala.conf
NGINX_LINK=/etc/nginx/sites-enabled/taminkala.conf
NGINX_SNIPPETS=/etc/nginx/snippets
CMD_LINK=/usr/local/bin/taminkala

# ---------- مقادیر پیش‌فرض (در اولین نصب پرسیده می‌شوند) ----------
REPO_URL="https://github.com/User-BH/taminkala.git"
BRANCH="main"
# اگر اسکریپت از داخل یک کپی مخزن اجرا شود، آدرس و شاخه همان کپی پیش‌فرض می‌شود
if _src=$(git -C "${TKB_SRC_DIR:-.}" rev-parse --show-toplevel 2>/dev/null); then
  _u=$(git -C "$_src" config --get remote.origin.url 2>/dev/null || true)
  _b=$(git -C "$_src" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
  [[ -n $_u ]] && REPO_URL=$_u
  [[ -n $_b && $_b != HEAD ]] && BRANCH=$_b
fi
APP_DIR="/opt/taminkala"
SERVER_NAME="_"
SITE_PORT="80"
PICHAK_PORT="8081"
PICHAK_UPSTREAM="127.0.0.1:8088"
BIME_PORT="8082"
BIME_ROOT="/var/www/bime"

# ---------- خروجی رنگی ----------
if [[ -t 1 ]]; then
  R=$'\e[31m'; G=$'\e[32m'; Y=$'\e[33m'; B=$'\e[36m'; W=$'\e[1m'; N=$'\e[0m'
else
  R=; G=; Y=; B=; W=; N=
fi
say()  { printf '%s\n' "${B}▸${N} $*"; }
ok()   { printf '%s\n' "${G}✔${N} $*"; }
warn() { printf '%s\n' "${Y}⚠${N} $*"; }
die()  { printf '%s\n' "${R}✘ $*${N}" >&2; exit 1; }
line() { printf '%s\n' "${B}──────────────────────────────────────────${N}"; }

trap 'die "خطا در خط $LINENO. عملیات متوقف شد؛ تغییری نیمه‌کاره اعمال نشده است."' ERR

need_root() { [[ $EUID -eq 0 ]] || die "این اسکریپت را با sudo اجرا کنید:  sudo $0 ${1:-}"; }

# پرسش با مقدار پیش‌فرض:  ask VAR "سؤال"
# ترمینال برای پرسش‌ها (اگر نباشد، مقادیر پیش‌فرض بدون پرسش استفاده می‌شوند)
if { : </dev/tty; } 2>/dev/null; then TTY=/dev/tty; else TTY=; fi

ask() {
  local __var=$1 __q=$2 __def=${!1} __ans
  if [[ -n $TTY ]]; then
    read -r -p "  $__q [${__def}]: " __ans <"$TTY" || true
  else
    printf '  %s: %s\n' "$__q" "$__def"
  fi
  printf -v "$__var" '%s' "${__ans:-$__def}"
}
confirm() { local a=; [[ -z $TTY ]] || read -r -p "  $1 [y/N]: " a <"$TTY" || true; [[ $a == [yY] || $a == yes || $a == بله ]]; }

valid_port() { [[ $1 =~ ^[0-9]+$ ]] && (( $1 >= 1 && $1 <= 65535 )); }

load_conf() { [[ -f $CONF_FILE ]] && source "$CONF_FILE"; return 0; }
save_conf() {
  mkdir -p "$CONF_DIR"
  cat > "$CONF_FILE" <<EOF
# تنظیمات نصب تأمین کالا باختر — با «sudo taminkala settings» تغییر دهید
REPO_URL="$REPO_URL"
BRANCH="$BRANCH"
APP_DIR="$APP_DIR"
SERVER_NAME="$SERVER_NAME"
SITE_PORT="$SITE_PORT"
PICHAK_PORT="$PICHAK_PORT"
PICHAK_UPSTREAM="$PICHAK_UPSTREAM"
BIME_PORT="$BIME_PORT"
BIME_ROOT="$BIME_ROOT"
EOF
  chmod 600 "$CONF_FILE"
}

ask_settings() {
  line; say "${W}تنظیمات${N} (برای قبول مقدار داخل کروشه فقط Enter بزنید)"
  ask REPO_URL        "آدرس مخزن گیت"
  ask BRANCH          "شاخه (branch)"
  ask APP_DIR         "پوشه نصب سایت"
  ask SERVER_NAME     "دامنه سایت (اگر ندارید _ بگذارید)"
  ask SITE_PORT       "پورت سایت اصلی"
  ask PICHAK_PORT     "پورت سامانه پیچک"
  ask PICHAK_UPSTREAM "آدرس داخلی برنامه پیچک (PICHAK_BIND)"
  ask BIME_PORT       "پورت سامانه بیمه و حواله"
  ask BIME_ROOT       "پوشه فایل‌های بیمه و حواله"
  for p in "$SITE_PORT" "$PICHAK_PORT" "$BIME_PORT"; do valid_port "$p" || die "پورت نامعتبر: $p"; done
  [[ $(printf '%s\n' "$SITE_PORT" "$PICHAK_PORT" "$BIME_PORT" | sort -u | wc -l) -eq 3 ]] || die "پورت‌ها باید با هم فرق داشته باشند."
  [[ ${PICHAK_UPSTREAM##*:} != "$PICHAK_PORT" ]] || die "پورت پیچک نباید با پورت داخلی برنامه پیچک یکی باشد."
  save_conf
  ok "تنظیمات در $CONF_FILE ذخیره شد."
}

ensure_packages() {
  local missing=()
  for p in git nginx curl; do command -v "$p" >/dev/null 2>&1 || missing+=("$p"); done
  ((${#missing[@]})) || return 0
  command -v apt-get >/dev/null || die "بسته‌های ${missing[*]} نصب نیستند و apt-get هم پیدا نشد."
  say "نصب بسته‌های لازم: ${missing[*]}"
  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}" >/dev/null
  ok "بسته‌ها نصب شدند."
}

# پورتی که برنامه دیگری (غیر از nginx) روی آن گوش می‌دهد
port_owner() { { ss -Hltnp "sport = :$1" 2>/dev/null | grep -o 'users:(("[^"]*' | head -1 | cut -d'"' -f2; } || true; }
check_ports() {
  for p in "$SITE_PORT" "$PICHAK_PORT" "$BIME_PORT"; do
    local o; o=$(port_owner "$p")
    [[ -z $o || $o == nginx ]] || die "پورت $p در حال استفاده توسط «$o» است. پورت دیگری در تنظیمات انتخاب کنید."
  done
}

git_safe() { git -c safe.directory="$APP_DIR" -C "$APP_DIR" "$@"; }
current_commit() { git_safe rev-parse --short HEAD 2>/dev/null || echo "-"; }

fetch_code() {
  if [[ -d $APP_DIR/.git ]]; then
    say "دریافت آخرین نسخه از مخزن ($BRANCH)…"
    git_safe fetch --quiet origin "$BRANCH" || die "دریافت از مخزن ناموفق بود. اتصال اینترنت یا دسترسی مخزن را بررسی کنید."
    # اگر کسی روی سرور فایلی از مخزن را دستی تغییر داده، قبل از بازنویسی پشتیبان می‌گیریم
    if ! git_safe diff --quiet HEAD; then
      mkdir -p "$BACKUP_DIR"
      local f="$BACKUP_DIR/local-changes-$(date +%Y%m%d-%H%M%S).patch"
      git_safe diff HEAD > "$f"
      warn "تغییرات دستی روی سرور پیدا شد؛ پشتیبان در $f ذخیره شد."
    fi
    git_safe reset --quiet --hard "origin/$BRANCH"
  else
    [[ ! -e $APP_DIR ]] || [[ -z $(ls -A "$APP_DIR") ]] || die "پوشه $APP_DIR وجود دارد و خالی نیست. پوشه دیگری انتخاب کنید."
    say "دریافت سایت از مخزن…"
    if ! git clone --quiet --branch "$BRANCH" "$REPO_URL" "$APP_DIR"; then
      cat >&2 <<EOF
${R}✘ دریافت مخزن ناموفق بود.${N}
  اگر مخزن خصوصی است یکی از این دو راه را انجام دهید:
   ۱) کلید SSH:  ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
      محتوای /root/.ssh/id_ed25519.pub را در GitHub → Settings → Deploy keys مخزن اضافه کنید
      و آدرس مخزن را به شکل git@github.com:User-BH/taminkala.git وارد کنید.
   ۲) توکن:  آدرس را به شکل https://<TOKEN>@github.com/User-BH/taminkala.git وارد کنید
      (توکن فقط با دسترسی خواندن همین مخزن).
EOF
      exit 1
    fi
  fi
  chmod -R a+rX "$APP_DIR"
  ok "نسخه فعلی سایت: $(current_commit)"
}

render() {  # render <template> <output>
  sed -e "s|{{SITE_PORT}}|$SITE_PORT|g" \
      -e "s|{{PICHAK_PORT}}|$PICHAK_PORT|g" \
      -e "s|{{PICHAK_UPSTREAM}}|$PICHAK_UPSTREAM|g" \
      -e "s|{{BIME_PORT}}|$BIME_PORT|g" \
      -e "s|{{BIME_ROOT}}|$BIME_ROOT|g" \
      -e "s|{{SITE_ROOT}}|$APP_DIR/public|g" \
      -e "s|{{SERVER_NAME}}|$SERVER_NAME|g" "$1" > "$2"
  # سرورهایی که IPv6 ندارند
  [[ -e /proc/net/if_inet6 ]] || sed -i '/listen \[::\]/d' "$2"
}

reload_nginx() {
  if [[ -d /run/systemd/system ]]; then
    systemctl enable --quiet nginx 2>/dev/null || true
    if systemctl is-active --quiet nginx; then systemctl reload nginx; else systemctl start nginx; fi
  else
    if [[ -s /run/nginx.pid ]] && kill -0 "$(cat /run/nginx.pid)" 2>/dev/null; then nginx -s reload 2>/dev/null; else nginx; fi
  fi
}

apply_nginx() {
  say "اعمال پیکربندی Nginx…"
  local tpl=$APP_DIR/deploy/nginx stamp; stamp=$(date +%Y%m%d-%H%M%S)
  mkdir -p "$BACKUP_DIR" "$NGINX_SNIPPETS" "$BIME_ROOT"
  chmod -R a+rX "$BIME_ROOT"           # فایل کپی‌شده با scp ممکن است برای Nginx قابل خواندن نباشد
  # پشتیبان از پیکربندی فعلی برای برگشت در صورت خطا
  local saved=()
  for f in "$NGINX_SITE" "$NGINX_SNIPPETS"/taminkala-*.conf; do
    if [[ -f $f ]]; then cp "$f" "$BACKUP_DIR/$(basename "$f").$stamp"; saved+=("$f"); fi
  done

  render "$tpl/taminkala.conf.template" "$NGINX_SITE"
  for t in "$tpl"/snippets/*.conf.template; do
    render "$t" "$NGINX_SNIPPETS/$(basename "${t%.template}")"
  done
  ln -sfn "$NGINX_SITE" "$NGINX_LINK"
  if [[ $SITE_PORT == 80 && -L /etc/nginx/sites-enabled/default ]]; then
    rm -f /etc/nginx/sites-enabled/default
    warn "سایت پیش‌فرض Nginx غیرفعال شد (فایل اصلی آن در sites-available باقی است)."
  fi

  if ! nginx -t >/tmp/taminkala-nginx-test.log 2>&1; then
    cat /tmp/taminkala-nginx-test.log >&2
    for f in "${saved[@]}"; do cp "$BACKUP_DIR/$(basename "$f").$stamp" "$f"; done
    ((${#saved[@]})) || rm -f "$NGINX_LINK"
    die "پیکربندی Nginx خطا داشت؛ تنظیمات قبلی برگردانده شد و سایت فعلی دست‌نخورده ماند."
  fi
  reload_nginx
  ok "Nginx به‌روز شد."
}

open_firewall() {
  command -v ufw >/dev/null 2>&1 || return 0
  ufw status 2>/dev/null | grep -q "Status: active" || return 0
  for p in "$SITE_PORT" "$PICHAK_PORT" "$BIME_PORT"; do ufw allow "$p/tcp" >/dev/null; done
  ok "پورت‌های $SITE_PORT، $PICHAK_PORT و $BIME_PORT در فایروال (ufw) باز شدند."
}

install_cmd() {
  ln -sfn "$APP_DIR/deploy/taminkala.sh" "$CMD_LINK"
  chmod +x "$APP_DIR/deploy/taminkala.sh"
}

http_code() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$1" || true; }
check() {  # check <عنوان> <آدرس> <کد مورد انتظار>
  local c; c=$(http_code "$2")
  if [[ $c == "$3" ]]; then ok "$1  ($c)"; else warn "$1  — انتظار $3، دریافت ${c:-بدون پاسخ}"; fi
}

health() {
  line; say "${W}بررسی سلامت${N}"
  check "سایت اصلی"                      "http://127.0.0.1:$SITE_PORT/"           200
  check "صفحه ۴۰۴ برای /pichak"           "http://127.0.0.1:$SITE_PORT/pichak"     404
  check "سامانه پیچک (پورت $PICHAK_PORT)"  "http://127.0.0.1:$PICHAK_PORT/"         200
  check "سامانه بیمه و حواله (پورت $BIME_PORT)" "http://127.0.0.1:$BIME_PORT/"      200
  [[ -f $BIME_ROOT/index.html ]] || warn "فایل $BIME_ROOT/index.html وجود ندارد؛ فایل HTML بیمه و حواله را با همین نام آنجا کپی کنید."
  [[ $(http_code "http://$PICHAK_UPSTREAM/api/health") == 200 ]] || warn "برنامه پیچک روی $PICHAK_UPSTREAM پاسخ نمی‌دهد؛ سرویس پیچک را بررسی کنید."
}

# ================== دستورها ==================
cmd_install() {
  need_root install
  line; printf '%s\n' "${W}  نصب سایت تأمین کالا باختر${N}"
  load_conf
  ensure_packages
  ask_settings
  check_ports
  fetch_code
  apply_nginx
  open_firewall
  install_cmd
  health
  line
  ok "${W}نصب کامل شد.${N} از این به بعد برای به‌روزرسانی بنویسید:  ${W}sudo taminkala update${N}"
}

cmd_update() {
  need_root update
  [[ -f $CONF_FILE ]] || die "سایت هنوز نصب نشده است. ابتدا:  sudo bash $0 install"
  load_conf
  local before; before=$(current_commit)
  mkdir -p "$BACKUP_DIR"; echo "$before" > "$CONF_DIR/previous_commit"
  fetch_code
  local after; after=$(current_commit)
  if [[ $before == "$after" ]]; then
    ok "سایت از قبل به‌روز است (نسخه $after)."
  else
    say "تغییرات این به‌روزرسانی:"
    git_safe log --oneline "$before..$after" 2>/dev/null | sed 's/^/    /' || true
  fi
  # ادامه کار با نسخه جدید همین اسکریپت (ممکن است در به‌روزرسانی تغییر کرده باشد)
  rm -f "$TKB_RUNNING_COPY"
  exec env -u TKB_RUNNING_COPY bash "$APP_DIR/deploy/taminkala.sh" _after_update
}

cmd_after_update() {
  need_root update
  load_conf
  apply_nginx
  install_cmd
  health
}

cmd_rollback() {
  need_root rollback
  load_conf
  local prev; prev=$(cat "$CONF_DIR/previous_commit" 2>/dev/null || true)
  [[ -n $prev && $prev != "-" ]] || die "نسخه قبلی ثبت نشده است."
  say "برگشت از نسخه $(current_commit) به $prev …"
  git_safe reset --quiet --hard "$prev"
  apply_nginx
  ok "سایت به نسخه $prev برگشت. (به‌روزرسانی بعدی دوباره آخرین نسخه را می‌گیرد.)"
}

cmd_status() {
  load_conf
  line; printf '%s\n' "${W}  وضعیت تأمین کالا باختر${N}"
  printf '  • %s %s\n' "نسخه سایت:" "$(current_commit) ($BRANCH)" \
                     "آخرین تغییر:" "$(git_safe log -1 --format='%cd — %s' --date=format:'%Y-%m-%d %H:%M' 2>/dev/null || echo -)" \
                     "پوشه سایت:" "$APP_DIR" \
                     "سایت اصلی:" "پورت $SITE_PORT" \
                     "پیچک:" "پورت $PICHAK_PORT → $PICHAK_UPSTREAM" \
                     "بیمه و حواله:" "پورت $BIME_PORT ← $BIME_ROOT"
  if [[ -d /run/systemd/system ]]; then
    printf '  • %s %s\n' "Nginx:" "$(systemctl is-active nginx 2>/dev/null || true)"
    local u; for u in $(systemctl list-units --all --plain --no-legend '*pichak*' 2>/dev/null | awk '{print $1}'); do
      printf '  • %s %s\n' "$u:" "$(systemctl is-active "$u" 2>/dev/null || true)"
    done
  fi
  health
}

cmd_settings() {
  need_root settings
  [[ -f $CONF_FILE ]] || die "سایت هنوز نصب نشده است. ابتدا:  sudo bash $0 install"
  load_conf
  ask_settings
  check_ports
  apply_nginx
  open_firewall
  health
}

cmd_help() {
  cat <<EOF
${W}استفاده:${N}  sudo taminkala [دستور]

  install    نصب اولیه (دریافت سایت از مخزن + تنظیم Nginx و پورت‌ها)
  update     به‌روزرسانی سایت با آخرین نسخه مخزن
  status     نمایش وضعیت و بررسی سلامت سرویس‌ها
  rollback   برگشت به نسخه قبل از آخرین به‌روزرسانی
  settings   تغییر پورت‌ها، دامنه و مسیرها
  help       همین راهنما

بدون دستور، منوی ساده نمایش داده می‌شود.
طراحی و توسعه: شرکت رهوار پیوند داده
EOF
}

menu() {
  line
  printf '%s\n' "${W}  تأمین کالا باختر — مدیریت سایت${N}"
  printf '%s\n' "  طراحی و توسعه: شرکت رهوار پیوند داده"
  line
  cat <<EOF
  1) نصب اولیه
  2) به‌روزرسانی از مخزن
  3) وضعیت و بررسی سلامت
  4) برگشت به نسخه قبل
  5) تغییر تنظیمات (پورت‌ها / دامنه)
  0) خروج
EOF
  [[ -n $TTY ]] || { cmd_help; exit 1; }
  local c; read -r -p "  انتخاب: " c <"$TTY" || true
  case $c in
    1) cmd_install ;; 2) cmd_update ;; 3) cmd_status ;;
    4) if confirm "مطمئن هستید؟"; then cmd_rollback; fi ;;
    5) cmd_settings ;; *) exit 0 ;;
  esac
}

case ${1:-} in
  install)  cmd_install ;;
  update)   cmd_update ;;
  status)   cmd_status ;;
  rollback) cmd_rollback ;;
  settings) cmd_settings ;;
  _after_update) cmd_after_update ;;
  help|-h|--help) cmd_help ;;
  "") menu ;;
  *) cmd_help; exit 1 ;;
esac
