"""Offline tests for captcha_math_ocr using real (non-sensitive) CBI captcha samples.

    python3 -m unittest test_captcha_ocr      (run inside this folder)
"""
import base64
import io
import json
import random
import time
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageOps

import captcha_math_ocr as ocr

HERE = Path(__file__).resolve().parent
SAMPLES = HERE / "samples"
LABELS = json.loads((SAMPLES / "labels.json").read_text(encoding="utf-8"))


def as_uri(image, fmt="JPEG"):
    buf = io.BytesIO()
    image.convert("RGB").save(buf, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def file_uri(name):
    return "data:image/jpeg;base64," + base64.b64encode((SAMPLES / name).read_bytes()).decode()


class RealSamples(unittest.TestCase):
    def test_every_sample_is_correct_or_abstains(self):
        right = 0
        for name, expr in LABELS.items():
            result = ocr.solve(file_uri(name))
            if result is not None:
                self.assertEqual(result["expression"], expr, name)
                a, b = map(int, expr.split("+"))
                self.assertEqual(result["answer"], str(a + b))
                right += 1
        self.assertGreaterEqual(right, len(LABELS) - 1)

    def test_small_shift_still_reads(self):
        image = Image.open(SAMPLES / "captcha-01.jpg").convert("RGB")
        shifted = ImageChops.offset(image, 2, 1)
        result = ocr.solve(as_uri(shifted))
        self.assertIsNotNone(result)
        self.assertEqual(result["expression"], "86+1")

    def test_old_keyword_argument_is_accepted(self):
        self.assertIsNotNone(ocr.solve(file_uri("captcha-01.jpg"), ocr_engine=None))

    def test_fast_enough(self):
        start = time.perf_counter()
        ocr.solve(file_uri("captcha-02.jpg"))
        self.assertLess(time.perf_counter() - start, 1.5)


class Abstains(unittest.TestCase):
    def test_blank_image(self):
        self.assertIsNone(ocr.solve(as_uri(Image.new("RGB", (130, 30), "white"))))

    def test_random_noise(self):
        rnd = random.Random(7)
        img = Image.new("RGB", (130, 30))
        img.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(130 * 30)])
        self.assertIsNone(ocr.solve(as_uri(img)))

    def test_unexpected_layout(self):
        mirrored = ImageOps.mirror(Image.open(SAMPLES / "captcha-07.jpg"))
        self.assertIsNone(ocr.solve(as_uri(mirrored)))

    def test_invalid_inputs(self):
        for value in (None, "", "hello", "data:text/plain;base64,aGk=", "data:image/png;base64,"):
            self.assertIsNone(ocr.solve(value))

    def test_absurd_size(self):
        self.assertIsNone(ocr.solve(as_uri(Image.new("RGB", (2000, 30), "white"))))


if __name__ == "__main__":
    unittest.main()
