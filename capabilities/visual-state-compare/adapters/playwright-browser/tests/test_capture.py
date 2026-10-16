"""Black-box synthetic privacy and browser capture acceptance."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "capture.py"
SCHEMA = json.loads((ROOT / "schemas" / "browser-visual-capture.v1.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)


class BrowserCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "source").mkdir()
        (self.root / "output").mkdir()
        self.html = self.root / "source" / "fixture.html"
        self.html.write_text(
            '<!doctype html><title>Fixture</title><h1>Ready</h1><button>Go</button>'
            '<img src="https://external.example.org/tracker.png">', encoding="utf-8")
        self.image = self.root / "output" / "frame.png"
        self.receipt = self.root / "output" / "receipt.json"

    def run_cli(self, *extra, source=None):
        command = [sys.executable, str(ENTRY),
                   *(source if source is not None else ["--source-html", str(self.html)]),
                   "--privacy", "SYNTHETIC_PUBLIC", "--host-alias", "test-synthetic",
                   "--screenshot", str(self.image), "--receipt", str(self.receipt)]
        if os.environ.get("VSC_CHROMIUM_PATH"):
            command += ["--chromium-path", os.environ["VSC_CHROMIUM_PATH"]]
        process = subprocess.run(command + list(extra), text=True, capture_output=True, timeout=40)
        if self.receipt.exists():
            VALIDATOR.validate(json.loads(self.receipt.read_text(encoding="utf-8")))
        return process

    def status(self):
        return json.loads(self.receipt.read_text(encoding="utf-8"))["status"]

    def test_remote_source_requires_private_mode(self):
        process = self.run_cli(source=["--url", "https://example.org/page"])
        self.assertEqual(process.returncode, 2)
        self.assertEqual(self.status(), "PRIVACY_DENIED")
        self.assertFalse(self.image.exists())

    def test_url_explicit_origin_required(self):
        process = self.run_cli("--privacy", "PRIVATE_LOCAL_ONLY",
                               source=["--url", "https://example.org/page"])
        self.assertEqual(process.returncode, 2)
        self.assertEqual(self.status(), "ORIGIN_NOT_AUTHORIZED")

    def test_plain_http_public_host_denied(self):
        process = self.run_cli("--privacy", "PRIVATE_LOCAL_ONLY",
                               "--allow-origin", "http://example.org",
                               source=["--url", "http://example.org/"])
        self.assertEqual(process.returncode, 2)
        self.assertEqual(self.status(), "INVALID_SOURCE")

    def test_url_embedded_credentials_denied(self):
        process = self.run_cli("--privacy", "PRIVATE_LOCAL_ONLY",
                               "--allow-origin", "https://example.org",
                               source=["--url", "https://user:password@example.org/page"])
        self.assertEqual(process.returncode, 2)
        self.assertEqual(self.status(), "INVALID_SOURCE")
        self.assertNotIn("password", self.receipt.read_text())

    def test_existing_output_preserved(self):
        self.image.write_bytes(b"operator-data")
        process = self.run_cli()
        self.assertEqual(process.returncode, 2)
        self.assertEqual(self.status(), "OUTPUT_EXISTS")
        self.assertEqual(self.image.read_bytes(), b"operator-data")

    def test_missing_or_non_html_input_fails_closed(self):
        text = self.root / "wrong.txt"
        text.write_text("no html")
        process = self.run_cli(source=["--source-html", str(text)])
        self.assertEqual(process.returncode, 2)
        self.assertEqual(self.status(), "INVALID_SOURCE")

    def test_synthetic_output_outside_source_tree(self):
        unsafe = self.root / "source" / "receipt.json"
        process = self.run_cli("--receipt", str(unsafe))
        self.assertEqual(process.returncode, 2)
        self.assertFalse(self.image.exists())
        self.assertEqual(json.loads(unsafe.read_text())["status"], "OUTPUT_IN_SOURCE_TREE")

    def test_isolated_consumer_without_repository_internals(self):
        consumer = self.root / "consumer"
        consumer.mkdir()
        script = consumer / "capture.py"
        shutil.copyfile(ENTRY, script)
        process = subprocess.run([sys.executable, str(script), "--source-html",
            str(self.root / "not-found.html"), "--privacy", "SYNTHETIC_PUBLIC",
            "--host-alias", "isolated", "--screenshot", str(self.image),
            "--receipt", str(self.receipt)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(self.status(), "INVALID_SOURCE")

    def test_real_offline_browser_synthetic(self):
        if not os.environ.get("VSC_REQUIRE_BROWSER") and not os.environ.get("VSC_CHROMIUM_PATH"):
            self.skipTest("Browser test requires VSC_REQUIRE_BROWSER=1 or VSC_CHROMIUM_PATH")
        process = self.run_cli("--width", "320", "--height", "240")
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "CAPTURED")
        self.assertEqual(result["image"]["width"], 320)
        self.assertEqual(result["image"]["height"], 240)
        self.assertGreaterEqual(result["cross_origin_requests_blocked"], 1)
        self.assertEqual(result["action_authority"], "NONE")
        self.assertEqual(result["semantic_verdict"], "NOT_EVALUATED")
        self.assertEqual(result["accessibility"], "NOT_CAPTURED")
        for secret in (str(self.root), "external.example.org", "Ready", "password"):
            self.assertNotIn(secret, self.receipt.read_text())


if __name__ == "__main__":
    unittest.main()
