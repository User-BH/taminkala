"""Local OCR for the CBI Pichak arithmetic captcha ("NN + N = ?").

Designed by Rahvar Peyvand Dadeh (شرکت رهوار پیوند داده).

Why not tesseract: the captcha draws gray text over random colored circles.
Converting to grayscale merges the circles into the digits and tesseract
misreads nearly everything. Here we instead:

1. keep only *neutral gray* pixels (the text colour); colored circles vanish,
2. locate the fixed "+", "=", "?" glyphs to align the image,
3. match each digit cell against templates learned from real captchas
   (see captcha_templates.py / build_templates.py).

The result is a suggestion the user can see and correct. When the layout is
unexpected or two digits score too closely, we abstain (return None) rather
than guess, so the user simply types the answer as before.

Public API is unchanged: solve(image_data_uri) -> {"expression", "answer", ...} | None
Only Pillow is required.
"""
from __future__ import annotations

import base64
import io
import re

# --- text colour filter ----------------------------------------------------
TEXT_MAX_SATURATION = 25   # max(R,G,B) - min(R,G,B): text is neutral gray
TEXT_MAX_VALUE = 175       # text gray is ~100-170; background is white

# --- glyph cells and fixed layout (pixels, at the captcha's native size) ---
CELL_W, CELL_H = 12, 17
BASE_X, BASE_Y = 5, 7
LAYOUT = {"d1": 0, "d2": 11, "plus": 29, "d3": 49, "eq": 67, "q": 87}
ANCHORS = ("plus", "eq", "q")
DIGIT_SLOTS = ("d1", "d2", "d3")
SEARCH_X, SEARCH_Y = 4, 3  # how far the whole text may be shifted

# --- decision thresholds (calibrated with leave-one-out on real samples) ---
ANCHOR_MIN = 0.55   # "+", "=", "?" must clearly be where we expect them
DIGIT_MIN = 0.55    # best digit score
MARGIN_MIN = 0.09   # best digit must beat the runner-up by this much
EXTRA_PENALTY = 0.6

MAX_IMAGE_BYTES = 2_000_000


def text_mask(image):
    """Return a 2D list of 0/1: 1 where the pixel looks like captcha text."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            r, g, b = px[x, y]
            hi = max(r, g, b)
            row.append(1 if hi - min(r, g, b) <= TEXT_MAX_SATURATION and hi <= TEXT_MAX_VALUE else 0)
        rows.append(row)
    return rows


def crop(mask, x, y):
    """Cell of CELL_H x CELL_W at (x, y); outside the image counts as empty."""
    h, w = len(mask), len(mask[0])
    return [[mask[yy][xx] if 0 <= yy < h and 0 <= xx < w else 0
             for xx in range(x, x + CELL_W)] for yy in range(y, y + CELL_H)]


def match(cell, template):
    """Share of the template's ink found in the cell, minus stray ink.

    Template values are 0..9 (how often that pixel is ink across samples).
    Noise only *adds* pixels, so missing ink is penalised more than extra ink.
    """
    on = on_hit = off = off_hit = 0
    for crow, trow in zip(cell, template):
        for c, t in zip(crow, trow):
            t = int(t)
            if t >= 5:
                on += 1
                on_hit += c
            elif t <= 1:
                off += 1
                off_hit += c
    if not on:
        return 0.0
    return on_hit / on - EXTRA_PENALTY * (off_hit / off if off else 0.0)


def best_score(mask, x, y, template, wiggle=1):
    return max(match(crop(mask, x + dx, y + dy), template)
               for dx in range(-wiggle, wiggle + 1) for dy in range(-wiggle, wiggle + 1))


def locate(mask, templates):
    """Find the text offset using the fixed '+', '=', '?' glyphs."""
    best = None
    for oy in range(-SEARCH_Y, SEARCH_Y + 1):
        for ox in range(-SEARCH_X, SEARCH_X + 1):
            scores = [match(crop(mask, BASE_X + ox + LAYOUT[a], BASE_Y + oy), templates[a2])
                      for a, a2 in zip(ANCHORS, ("+", "=", "?"))]
            total = sum(scores)
            if best is None or total > best[0]:
                best = (total, ox, oy, scores)
    return best


def read_digit(mask, x, y, templates):
    ranked = sorted(((best_score(mask, x, y, t), ch) for ch, t in templates.items() if ch.isdigit()),
                    reverse=True)
    (s1, ch), (s2, _) = ranked[0], ranked[1]
    return ch, s1, s1 - s2


def recognize(image, templates):
    """Return (result_dict | None, details) for an already-opened PIL image."""
    mask = text_mask(image)
    total, ox, oy, anchor_scores = locate(mask, templates)
    details = {"offset": (ox, oy), "anchors": [round(s, 3) for s in anchor_scores], "digits": []}
    if min(anchor_scores) < ANCHOR_MIN:
        details["reason"] = "layout"
        return None, details
    digits = []
    for slot in DIGIT_SLOTS:
        ch, score, margin = read_digit(mask, BASE_X + ox + LAYOUT[slot], BASE_Y + oy, templates)
        details["digits"].append((ch, round(score, 3), round(margin, 3)))
        if score < DIGIT_MIN or margin < MARGIN_MIN:
            details["reason"] = f"uncertain:{slot}"
            return None, details
        digits.append(ch)
    a, b = int(digits[0] + digits[1]), int(digits[2])
    confidence = min(m for _, _, m in details["digits"])
    return {"expression": f"{a}+{b}", "answer": str(a + b), "confidence": round(confidence, 3)}, details


def parse_expression(text: str):
    """Kept for compatibility with older callers/tests."""
    clean = re.sub(r"\s+", "", text or "").replace("×", "*").replace("−", "-")
    clean = re.sub(r"(?:=\??|\?)$", "", clean)
    found = re.fullmatch(r"(\d{1,2})([+*\-])(\d{1,2})", clean)
    if not found:
        return None
    a, op, b = int(found[1]), found[2], int(found[3])
    value = a + b if op == "+" else a * b if op == "*" else a - b
    return {"expression": f"{a}{op}{b}", "answer": str(value)} if 0 <= value <= 9999 else None


def solve(image_data_uri: str, *, templates=None, **_ignored):
    """Return {"expression", "answer", "confidence"} or None (abstain)."""
    if not isinstance(image_data_uri, str) or not image_data_uri.startswith("data:image/") \
            or ";base64," not in image_data_uri:
        return None
    from PIL import Image

    raw = base64.b64decode(image_data_uri.split(";base64,", 1)[1], validate=True)
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        return None
    image = Image.open(io.BytesIO(raw))
    if not (60 <= image.width <= 400 and 15 <= image.height <= 120):
        return None
    if templates is None:
        from captcha_templates import TEMPLATES as templates
    result, _ = recognize(image, templates)
    return result
