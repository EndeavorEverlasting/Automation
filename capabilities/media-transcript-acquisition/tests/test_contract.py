"""Independent JSON Schema and isolated-consumer acceptance tests."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/transcript-evidence.v1.schema.json").read_text())
Draft202012Validator.check_schema(SCHEMA)
VALIDATE = Draft202012Validator(SCHEMA)
VTT = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello!\n"


class ContractTests(unittest.TestCase):
    def test_isolated_consumer_and_verified_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standalone = root / "acquire.py"
            shutil.copyfile(ROOT / "acquire.py", standalone)
            (root / "captions.vtt").write_text(VTT)
            output = root / "receipt.json"
            result = subprocess.run(
                [sys.executable, str(standalone), "--url",
                 "https://www.youtube.com/shorts/pl0EltNU5p0",
                 "--strategy", "offline", "--captions-file", str(root / "captions.vtt"),
                 "--out", str(output)], cwd=root, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(output.read_text())
            VALIDATE.validate(receipt)
            self.assertEqual(receipt["proof_ceiling"], "SOURCE_TEXT_ACQUIRED")

    def test_schema_rejects_false_success(self):
        forged = {
            "contract": "automation.media-transcript-evidence/v1",
            "status": "TRANSCRIPT_ACQUIRED", "method": None, "attempts": [],
            "cues": [], "proof_ceiling": "NO_SOURCE_TEXT"
        }
        self.assertFalse(VALIDATE.is_valid(forged))


if __name__ == "__main__":
    unittest.main()
