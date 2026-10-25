"""Safe offline tests with synthetic (non-bank) HTML fragments."""
import unittest
from bs4 import BeautifulSoup
from captcha_inline import extract_inline_captcha_source


def extract(html):
    return extract_inline_captcha_source(BeautifulSoup(html, "html.parser"))


class InlineCaptchaTests(unittest.TestCase):
    def test_known_target_with_empty_image_src(self):
        html = """<img id='ctl00_ucBody_ucContent_ctl00_imgcpatcha' src=''>
        <script>document.getElementById("ctl00_ucBody_ucContent_ctl00_imgcpatcha")
           .setAttribute("src", 'data:image/jpeg;base64,/9j/4AAQSkZJRg==');</script>"""
        self.assertEqual(extract(html), "data:image/jpeg;base64,/9j/4AAQSkZJRg==")

    def test_unrelated_image_is_not_selected(self):
        html = """<script>document.getElementById("other")
           .setAttribute("src", 'data:image/jpeg;base64,/9j/4AAQSkZJRg==');</script>"""
        self.assertEqual(extract(html), "")

    def test_no_inline_script_or_external_script(self):
        self.assertEqual(extract('<script src="/external.js"></script>'), "")

    def test_alternate_quotes_and_whitespace(self):
        html = """<script> document.getElementById('ctl00_ucBody_ucContent_ctl00_imgcpatcha')
           .setAttribute( 'src' , "data:image/png;base64,iVBORw0KGgo=" ) ;</script>"""
        self.assertEqual(extract(html), "data:image/png;base64,iVBORw0KGgo=")


if __name__ == "__main__":
    unittest.main()
