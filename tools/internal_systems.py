"""Bring an internal tool (single HTML file) into the company look and put it on the internal port.

    python3 tools/internal_systems.py <source.html> <slug> "<header title>"

Writes bime/<slug>/index.html, served at http://<server>:8082/<slug>/ (company network only).
- embedded Vazirmatn font and logo images -> the shared files in public/assets
- shared theme (assets/css/systems.css) and the header with a link back to the systems list
The tool's own logic, storage and print layout are left as they are.
Designed and developed by Rahvar Peyvand Dadeh
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACK = ('<a class="sys-back" href="/" title="بازگشت به فهرست سامانه‌ها">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>'
        '<rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>'
        '<span>سامانه‌ها</span></a>')


def convert(src: Path, slug: str, title: str) -> Path:
    s = src.read_text(encoding="utf-8")
    # shared font and logo instead of ~150 KB + ~45 KB per copy embedded in every page
    s = re.sub(r'@font-face\{font-family:"?Vazirmatn"?;src:url\("?data:font/woff2;base64,[A-Za-z0-9+/=]+"?\) format\("woff2"\);[^}]*\}', "", s)
    s = re.sub(r'(<link rel="icon"[^>]*href=")data:image/png;base64,[A-Za-z0-9+/=]+', r"\1/assets/img/favicon-32.png", s)
    s = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "/assets/img/logo-192.webp", s)
    assert "data:font/woff2" not in s, "font not replaced"

    head_add = ('  <meta name="robots" content="noindex, nofollow">\n'
                '  <link rel="stylesheet" href="/assets/css/systems.css">\n')
    # the document's own tags are the LAST </head> and the <body> after it; bundled libraries
    # (SheetJS) contain "</head><body>" inside JavaScript strings, which must not be touched
    h = s.rindex("</head>")
    s = s[:h] + head_add + s[h:]
    e = s.rindex("</body>")
    s = s[:e] + '<script src="/assets/js/systems.js"></script>\n' + s[e:]
    body_at = s.index("<body", s.rindex("</head>"))

    if '<header class="topbar">' in s or '<header class="site-header">' in s:
        # existing header: add the back link next to its status pill
        m = re.search(r'(<div class="(?:offline-pill|header-tag)">.*?</div>)', s, re.S)
        assert m, "status pill not found"
        s = s.replace(m.group(1), '<div class="sys-tools">' + m.group(1) + BACK + "</div>", 1)
    else:
        bar = ('<header class="sys-bar"><div class="sys-bar-in"><div class="sys-brand">'
               '<img src="/assets/img/logo-192.webp" alt="لوگوی تأمین کالا باختر" width="58" height="58">'
               f'<div><span>شرکت تأمین کالا باختر</span><h1>{title}</h1></div></div>'
               f'<div class="sys-tools">{BACK}</div></div></header>\n')
        m = re.compile(r"<body([^>]*)>").match(s, body_at)
        s = s[:body_at] + f'<body{m.group(1)} class="sys-{slug}">\n' + bar + s[m.end():]

    out = ROOT / "bime" / slug / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(s, encoding="utf-8")
    return out


if __name__ == "__main__":
    src, slug, title = sys.argv[1], sys.argv[2], sys.argv[3]
    out = convert(Path(src), slug, title)
    print(out.relative_to(ROOT), f"{Path(src).stat().st_size // 1024} KB -> {out.stat().st_size // 1024} KB")
