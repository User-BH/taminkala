"""Extract ONLY the captcha image data URI assigned to the known CBI DOM node.

The public ASP.NET page embeds the JPEG in an inline script instead of putting
it in the initial <img src>. No JS runtime or POST is needed to read the literal.
"""
import re

CAPTCHA_ID = "ctl00_ucBody_ucContent_ctl00_imgcpatcha"

# Explicit DOM target, literal value and image MIME type: avoids picking up
# unrelated data URLs elsewhere in page scripts.
_CAPTURE = re.compile(
    r"""\bdocument\s*\.\s*getElementById\s*\(\s*(['\"])"""
    + re.escape(CAPTCHA_ID)
    + r"""\1\s*\)\s*\.\s*setAttribute\s*\(\s*(['\"])src\2\s*,\s*(['\"])(data:image/(?:jpeg|jpg|png|gif|webp);base64,[A-Za-z0-9+/=]+)\3\s*\)""",
    re.IGNORECASE,
)


def extract_inline_captcha_source(soup):
    """Return an image data URI or empty string, without executing scripts."""
    for script in soup.find_all("script"):
        if script.get("src"):
            continue
        javascript = script.string or script.get_text() or ""
        match = _CAPTURE.search(javascript)
        if match:
            return match.group(4)
    return ""
