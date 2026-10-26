"""Generate responsive WebP copies of the site images.

    python3 tools/images.py

For every JPG/WebP master in public/assets/img/{photos,brands} it writes
public/assets/img/<dir>/w/<name>-<width>.webp for the widths below (never upscaled),
plus small logo files. Run it again after adding or replacing a photo.
Designed and developed by Rahvar Peyvand Dadeh
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "public" / "assets" / "img"
WIDTHS = (480, 800, 1200, 1600, 2000)


def webp(im, out, width, quality=78):
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(out, "WEBP", quality=quality, method=6)


def main():
    for folder in ("photos", "brands"):
        src_dir = ROOT / folder
        out_dir = src_dir / "w"
        out_dir.mkdir(exist_ok=True)
        for src in sorted(list(src_dir.glob("*.jpg")) + list(src_dir.glob("*.webp"))):
            if src.stem.endswith("-1200"):          # old hand-made size, not a master
                continue
            im = Image.open(src).convert("RGB")
            for w in [w for w in WIDTHS if w < im.width] + [im.width]:   # never upscaled; full size included
                webp(im, out_dir / f"{src.stem}-{w}.webp", w)
            print(src.name, im.size)
    logo = Image.open(ROOT / "logo.png").convert("RGBA")
    for size in (96, 192):
        small = logo.resize((size, size), Image.LANCZOS)
        small.save(ROOT / f"logo-{size}.webp", "WEBP", quality=88, method=6)
        small.save(ROOT / f"logo-{size}.png", optimize=True)
    # social preview 1200x630: office photo with the logo
    og = Image.open(ROOT / "photos" / "office-with-sign.webp").convert("RGB")
    scale = max(1200 / og.width, 630 / og.height)
    og = og.resize((round(og.width * scale), round(og.height * scale)), Image.LANCZOS)
    left, top = (og.width - 1200) // 2, (og.height - 630) // 2
    og = og.crop((left, top, left + 1200, top + 630))
    badge = logo.resize((150, 150), Image.LANCZOS)
    og.paste(badge, (1200 - 150 - 40, 40), badge)
    og.save(ROOT / "og-image.jpg", quality=84, optimize=True, progressive=True)


if __name__ == "__main__":
    main()
