"""Offline black-box tests; the consumer only knows the documented CLI."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "compare.py"


class VisualStateCompareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.before = self.dir / "baseline.png"
        self.after = self.dir / "candidate.png"
        self.receipt = self.dir / "receipt.json"
        Image.new("RGB", (8, 8), "white").save(self.before)
        Image.new("RGB", (8, 8), "white").save(self.after)

    def run_compare(self, *options):
        proc = subprocess.run(
            [sys.executable, str(ENTRY), "--before", str(self.before),
             "--after", str(self.after), "--receipt", str(self.receipt), *options],
            text=True, capture_output=True, check=False
        )
        return proc, json.loads(self.receipt.read_text(encoding="utf-8"))

    def change_pixel(self, x=3, y=2, color="black"):
        image = Image.open(self.after)
        image.putpixel((x, y), Image.new("RGB", (1, 1), color).getpixel((0, 0)))
        image.save(self.after)

    def test_identical(self):
        proc, result = self.run_compare()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(result["status"], "NO_CHANGE")
        self.assertEqual(result["changed_pixels"], 0)
        self.assertEqual(result["change_ratio"], 0.0)
        self.assertEqual(result["semantic_verdict"], "NOT_EVALUATED")

    def test_single_pixel(self):
        self.change_pixel()
        proc, result = self.run_compare("--diff-out", str(self.dir / "diff.png"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(result["status"], "CHANGED")
        self.assertEqual(result["changed_pixels"], 1)
        self.assertEqual(result["change_ratio"], 1 / 64)
        self.assertEqual(result["changed_bbox"], {"x": 3, "y": 2, "width": 1, "height": 1})
        self.assertTrue((self.dir / "diff.png").is_file())

    def test_masked_dynamic_region(self):
        self.change_pixel()
        proc, result = self.run_compare("--mask", "2,1,3,3")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(result["status"], "NO_CHANGE")
        self.assertEqual(result["comparable_pixels"], 55)

    def test_diff_ratio_policy(self):
        self.change_pixel()
        proc, result = self.run_compare("--max-diff-ratio", "0.02")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(result["status"], "TOLERATED_CHANGE")
        self.assertEqual(result["changed_pixels"], 1)

    def test_channel_difference_not_luma_blind(self):
        self.change_pixel(color=(0, 255, 0))
        proc, result = self.run_compare()
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(result["changed_pixels"], 1)

    def test_pixel_threshold(self):
        self.change_pixel(color=(254, 254, 254))
        proc, result = self.run_compare("--pixel-threshold", "1")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(result["status"], "NO_CHANGE")

    def test_geometry_mismatch(self):
        Image.new("RGB", (9, 8), "white").save(self.after)
        proc, result = self.run_compare()
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "INCOMPARABLE_GEOMETRY")

    def test_invalid_image(self):
        self.after.write_bytes(b"not an image")
        proc, result = self.run_compare()
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertNotIn(str(self.after), json.dumps(result))

    def test_unsupported_format(self):
        Image.new("RGB", (8, 8), "white").save(self.after, format="JPEG")
        proc, result = self.run_compare()
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "INVALID_INPUT")

    def test_invalid_mask(self):
        proc, result = self.run_compare("--mask", "7,7,2,2")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "INVALID_MASK")

    def test_all_pixels_masked(self):
        proc, result = self.run_compare("--mask", "0,0,8,8")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "INVALID_MASK")

    def test_deterministic_receipt(self):
        self.change_pixel()
        _, first = self.run_compare()
        _, second = self.run_compare()
        self.assertEqual(first, second)
        self.assertNotIn("absolute_path", json.dumps(first))


if __name__ == "__main__":
    unittest.main()
