"""Validate the media handoff with Automation's actual runtime contract."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.json"
VALIDATOR = ROOT / "scripts/validate_runtime_handoff.py"


class MediaArtifactHandoffTests(unittest.TestCase):
    def test_ready_packet_is_valid_and_private(self):
        proc = subprocess.run(
            [sys.executable, str(VALIDATOR), "--packet", str(PACKET), "--require-ready"],
            cwd=ROOT, capture_output=True, text=True, timeout=12
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["state"], "PASS")

    def test_unknown_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "packet.json"
            packet = json.loads(PACKET.read_text(encoding="utf-8"))
            packet["execution_environment"] = "UNKNOWN_RUNTIME"
            p.write_text(json.dumps(packet), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(VALIDATOR), "--packet", str(p), "--require-ready"],
                cwd=ROOT, capture_output=True, text=True, timeout=12
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stdout)["state"], "FAIL")


if __name__ == "__main__":
    unittest.main()
