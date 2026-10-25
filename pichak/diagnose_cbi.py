#!/usr/bin/env python3
"""Read-only network diagnosis. No captcha/financial data, cookie, or viewstate values are printed.
Use /opt/pichak/venv/bin/python /opt/pichak/diagnose_cbi.py
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

URL = 'https://cbi.ir/EstelamPichak/22036.aspx'

def describe_url(value, origin):
    if not value:
        return 'EMPTY'
    if value.startswith('data:'):
        return 'DATA_URI_image=' + str(value.lower().startswith('data:image/')) + '_length=' + str(len(value))
    if value.startswith('blob:') or value.startswith('javascript:'):
        return 'DYNAMIC_' + value.split(':')[0]
    absurl = urljoin(origin, value)
    parsed = urlparse(absurl)
    # never print query params: they may contain authentication tokens
    return f'URL host={parsed.hostname or "?"} path={parsed.path[:100]}'

try:
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0',
                      'Accept-Language': 'fa-IR,fa;q=0.9,en-US;q=0.7'})
    r = s.get(URL, timeout=(7, 25))
    print('HTTP_STATUS:', r.status_code)
    print('FINAL_HOST:', urlparse(r.url).hostname)
    print('FINAL_PATH:', urlparse(r.url).path)
    print('CONTENT_TYPE:', r.headers.get('Content-Type', '?').split(';')[0])
    print('RESPONSE_BYTES:', len(r.content))
    soup = BeautifulSoup(r.text, 'html.parser')
    title = soup.title.get_text(' ', strip=True)[:100] if soup.title else '(not found)'
    print('TITLE:', title)
    print('VIEWSTATE_PRESENT:', bool(soup.find('input', attrs={'name': '__VIEWSTATE'})))
    print('VIEWSTATEGENERATOR_PRESENT:', bool(soup.find('input', attrs={'name': '__VIEWSTATEGENERATOR'})))
    print('FORM_COUNT:', len(soup.find_all('form')))
    images = soup.find_all('img')
    print('IMAGES_COUNT:', len(images))
    for i, img in enumerate(images[:40], start=1):
        tag_id = str(img.get('id', ''))[:110]
        attr_str = ' '.join(str(img.get(k, '')) for k in ('id', 'name', 'class', 'alt', 'src', 'data-src'))
        interesting = bool(re.search(r'capt|cpatch|valid|secur', attr_str, flags=re.I))
        if interesting or len(images) <= 6:
            print('IMG:', i, 'id=', tag_id, 'interesting=', interesting,
                  'src=', describe_url(img.get('src') or img.get('data-src'), r.url))
    for term in ('imgcpatcha', 'captcha', 'cpatcha', '__doPostBack', 'cloudflare', 'Access Denied'):
        print('MENTIONS_' + term.upper() + ':', term.lower() in r.text.lower())
    print('NOTE: no cookies, hidden field values, captcha bytes or financial details have been printed.')
except requests.Timeout:
    print('ERROR: TIMEOUT')
except requests.SSLError:
    print('ERROR: SSL_VALIDATION_ERROR')
except requests.RequestException as e:
    print('ERROR: NETWORK', type(e).__name__)
except Exception as e:
    print('ERROR: PARSING', type(e).__name__)
