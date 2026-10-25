#!/usr/bin/env bash
# Build the Windows package and publish it on the "release" branch of origin
# (one commit, replaced each time):  TaminKala-windows.zip + VERSION.txt
#   bash windows/publish.sh
# The server's update.bat downloads it from there.
# Designed and developed by Rahvar Peyvand Dadeh
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
BRANCH=${RELEASE_BRANCH:-release}
OUT=$(mktemp -d)
bash "$REPO/windows/build.sh" "$OUT/dist"
VERSION=$(git -C "$REPO" rev-parse --short HEAD)
PUB=$OUT/pub
mkdir -p "$PUB"
mv "$OUT"/dist/TaminKala-windows-*.zip "$PUB/TaminKala-windows.zip"
echo "$VERSION" > "$PUB/VERSION.txt"
cat > "$PUB/README.md" <<MD
# بسته‌ی ویندوز تأمین کالا باختر

نسخه: \`$VERSION\` — $(date -u '+%Y-%m-%d %H:%M') UTC

- دانلود: فایل [TaminKala-windows.zip](TaminKala-windows.zip) ← دکمه‌ی Download (یا Raw)
- روی سرور: روی \`update.bat\` در \`C:\\TaminKala\` دوبار کلیک کنید.

این شاخه خودکار ساخته می‌شود؛ دستی تغییرش ندهید.
MD
git -C "$PUB" init -q -b "$BRANCH"
git -C "$PUB" add -A
git -C "$PUB" -c user.name="$(git -C "$REPO" config user.name || echo publisher)" -c user.email="$(git -C "$REPO" config user.email || echo publisher@localhost)" \
  commit -qm "Windows package $VERSION"
git -C "$PUB" push -q -f "$(git -C "$REPO" remote get-url origin)" "HEAD:refs/heads/$BRANCH"
echo "✔ published $VERSION to branch $BRANCH"
rm -rf "$OUT"
