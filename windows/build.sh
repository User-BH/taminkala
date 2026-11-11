#!/usr/bin/env bash
# Build the self-contained Windows package: TaminKala-windows-<version>.zip
#   bash windows/build.sh [output-dir]
# Needs internet once (Python embeddable + Windows wheels are cached in .cache/).
# Designed and developed by Rahvar Peyvand Dadeh
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$REPO/dist}
PYVER=3.12.10
CACHE=$REPO/.cache/windows
STAGE=$(mktemp -d)/TaminKala
VERSION=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d)
mkdir -p "$CACHE" "$OUT" "$STAGE"

echo "▸ Python $PYVER (embeddable, 64-bit)"
[[ -s $CACHE/python-$PYVER-embed-amd64.zip ]] || curl -fsSL -o "$CACHE/python-$PYVER-embed-amd64.zip" "https://www.python.org/ftp/python/$PYVER/python-$PYVER-embed-amd64.zip"
mkdir -p "$STAGE/python"
unzip -q "$CACHE/python-$PYVER-embed-amd64.zip" -d "$STAGE/python"
PTH=$(ls "$STAGE"/python/python3*._pth)
printf 'python312.zip\r\n.\r\nLib\\site-packages\r\n..\r\nimport site\r\n' > "$PTH"

echo "▸ packages (Windows wheels)"
python3 -m pip install -q --target "$STAGE/python/Lib/site-packages" --platform win_amd64 --python-version 3.12 \
  --implementation cp --only-binary=:all: --no-compile --cache-dir "$CACHE/pip" \
  flask waitress requests beautifulsoup4 pillow
rm -rf "$STAGE/python/Lib/site-packages/bin"

echo "▸ application"
cp -r "$REPO/public" "$REPO/bime" "$STAGE/"
mkdir -p "$STAGE/pichak"
cp -r "$REPO/pichak/static" "$STAGE/pichak/"
cp "$REPO"/pichak/{app.py,captcha_inline.py,index.html,logo.png} "$STAGE/pichak/"
cp "$REPO"/pichak-ocr/{captcha_math_ocr.py,captcha_templates.py} "$STAGE/pichak/"     # latest OCR engine
cp "$REPO/windows/server.py" "$REPO/windows/stats.py" "$STAGE/"
cp "$REPO"/windows/*.bat "$STAGE/"
cp -r "$REPO/windows/tools" "$STAGE/"
cp "$REPO/windows/README-FA.html" "$STAGE/راهنما.html"
find "$STAGE" -name '__pycache__' -prune -exec rm -rf {} +
find "$STAGE" -name '.gitkeep' -delete
echo "$VERSION" > "$STAGE/VERSION.txt"

ZIP="$OUT/TaminKala-windows-$VERSION.zip"
rm -f "$ZIP"
# Python's zipfile marks non-ASCII names as UTF-8, so Windows shows راهنما.html correctly
python3 - "$(dirname "$STAGE")" "$ZIP" <<'PY'
import os, sys, zipfile
base, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for d, _, files in os.walk(os.path.join(base, "TaminKala")):
        for f in sorted(files):
            full = os.path.join(d, f)
            z.write(full, os.path.relpath(full, base).replace(os.sep, "/"))
PY
echo "✔ $ZIP ($(du -h "$ZIP" | cut -f1))"
