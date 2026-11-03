"""VSC-2 OCR CLI: schema, negatives, and optional live-engine smoke."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "vision_cli.py"
SCHEMA = json.loads((ROOT / "schemas" / "visual-observation.v1.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)
FIXTURES = ROOT / "tests" / "fixtures" / "ocr"
LABELS = json.loads((FIXTURES / "labels.v1.json").read_text(encoding="utf-8"))
TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


class VisionOcrCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        if not (FIXTURES / "plain_serial.png").is_file():
            subprocess.run([sys.executable, str(ROOT / "tests" / "generate_ocr_fixtures.py")], check=True)

    def run_cli(self, *options, expect_receipt=True):
        output = self.dir / "observation.json"
        proc = subprocess.run(
            [sys.executable, str(CLI), "analyze", "--output", str(output), *options],
            text=True, capture_output=True, check=False,
        )
        receipt = None
        if expect_receipt and output.is_file():
            receipt = json.loads(output.read_text(encoding="utf-8"))
            VALIDATOR.validate(receipt)
            self.assertEqual(receipt["semantic_verdict"], "NOT_EVALUATED")
            self.assertEqual(receipt["action_authority"], "NONE")
        return proc, receipt

    def test_invalid_input_rejected(self):
        bad = self.dir / "note.txt"
        bad.write_text("not an image", encoding="utf-8")
        proc, receipt = self.run_cli("--input", str(bad), "--engine", "tesseract")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(receipt["status"], "INVALID_INPUT")
        self.assertEqual(receipt["proof_ceiling"], "OCR_NO_PROOF")

    def test_output_denied_when_exists(self):
        png = self.dir / "x.png"
        Image.new("RGB", (16, 16), "white").save(png)
        out = self.dir / "observation.json"
        out.write_text("{}", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(CLI), "analyze", "--input", str(png),
             "--output", str(out), "--engine", "tesseract"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("OUTPUT_DENIED", proc.stdout + proc.stderr)

    def test_paddle_unavailable_is_typed(self):
        png = FIXTURES / "blank.png"
        proc, receipt = self.run_cli(
            "--input", str(png), "--engine", "paddle", "--privacy", "SYNTHETIC_PUBLIC",
        )
        self.assertIn(receipt["status"], {"ENGINE_UNAVAILABLE", "OK", "NO_TEXT", "OCR_FAILED"})
        if receipt["status"] == "ENGINE_UNAVAILABLE":
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(receipt["proof_ceiling"], "OCR_ENGINE_UNAVAILABLE")
            self.assertEqual(receipt["regions"], [])

    def test_blank_fixture_no_text_or_unavailable(self):
        if not TESSERACT.is_file():
            self.skipTest("tesseract binary not installed")
        proc, receipt = self.run_cli(
            "--input", str(FIXTURES / "blank.png"),
            "--engine", "tesseract",
            "--tesseract-bin", str(TESSERACT),
            "--privacy", "SYNTHETIC_PUBLIC",
        )
        self.assertIn(receipt["status"], {"NO_TEXT", "OK"})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(receipt["action_authority"], "NONE")

    def test_tesseract_reads_synthetic_serial(self):
        if not TESSERACT.is_file():
            self.skipTest("tesseract binary not installed")
        proc, receipt = self.run_cli(
            "--input", str(FIXTURES / "plain_serial.png"),
            "--engine", "tesseract",
            "--tesseract-bin", str(TESSERACT),
            "--privacy", "SYNTHETIC_PUBLIC",
            "--lang", "eng",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(receipt["status"], "OK")
        joined = (receipt.get("full_text") or "").upper()
        self.assertIn("SERIAL", joined)
        self.assertTrue(receipt["regions"])
        self.assertEqual(receipt["proof_ceiling"], "OCR_INFERENCE_SMOKE")

    def test_holdout_labels_present(self):
        self.assertEqual(LABELS["contract_id"], "automation.visual-ocr-holdout/v1")
        for case in LABELS["cases"]:
            self.assertTrue((FIXTURES / case["image"]).is_file())


class CerHelperTests(unittest.TestCase):
    def test_cer_identity(self):
        sys.path.insert(0, str(ROOT))
        from ocr_common import character_error_rate
        self.assertEqual(character_error_rate("abc", "abc"), 0.0)
        self.assertGreater(character_error_rate("abc", "axc"), 0.0)


if __name__ == "__main__":
    unittest.main()
