"""No network or model dependency in CI; provider adapters are mocked."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import social_insights as s

CAPTIONS = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAn LED uses a resistor.\n\n"
REEL = "https://www.instagram.com/reel/DfOrNZxJkHI/?psln=unnecessary"


class SocialMediaTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.captions = self.root / "captions.vtt"
        self.captions.write_text(CAPTIONS, encoding="utf-8")
        self.out = self.root / "receipt.json"

    def call(self, *args):
        proc = subprocess.run([sys.executable, str(ROOT / "social_insights.py"),
                               "--url", REEL, "--out", str(self.out), *args],
                              text=True, capture_output=True, timeout=8, cwd=self.root)
        return proc, json.loads(self.out.read_text())

    def test_url_normalization(self):
        provider, source = s.normalize_source(REEL)
        self.assertEqual(provider, "instagram")
        self.assertEqual(source, "https://www.instagram.com/reel/DfOrNZxJkHI")
        self.assertEqual(s.normalize_source("https://youtube.com/watch?v=pl0EltNU5p0&t=100")[1],
                         "https://youtube.com/watch?v=pl0EltNU5p0")
        for bad in ("http://instagram.com/reel/abc", "https://instagram.com.evil.org/reel/x",
                    "https://instagram.com:444/reel/x", "file:///etc/passwd",
                    "https://instagram.com/accounts/login", "https://127.0.0.1/private",
                    "https://user:secret@instagram.com/reel/abc"):
            with self.subTest(url=bad):
                with self.assertRaises(s.AcquisitionError):
                    s.normalize_source(bad)

    def test_offline_reel_captions_receipt(self):
        proc, result = self.call("--strategy", "offline", "--captions-file", str(self.captions))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(result["status"], "EVIDENCE_READY")
        self.assertEqual(result["source"]["provider"], "instagram")
        self.assertEqual(result["cues"][0]["id"], "c0001")
        self.assertIn("resistor", result["cues"][0]["text"])
        self.assertFalse(result["insights"])
        self.assertNotIn("psln", json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(result["proof_ceiling"], "SOURCE_EVIDENCE_ACQUIRED_NOT_FACT_CHECKED")

    def test_no_source_does_not_fabricate(self):
        proc, result = self.call("--strategy", "offline")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "SOURCE_NOT_ATTACHED")
        self.assertEqual(result["insights"], [])

    def test_id_references_are_required_and_validated(self):
        cues = [{"start_ms": 1000, "end_ms": 3000, "text": "resistor"}]
        with patch.object(s, "infer_insights", return_value={"insights": [
             {"claim": "Resistor limits current", "evidence_ids": ["c0001"]},
             {"claim": "False citation", "evidence_ids": ["f9999"]},
             {"claim": "No citation", "evidence_ids": []}] }):
            results = s.analyze(cues, [], self.root, "local-model")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["verification"], "UNVERIFIED_TECHNICAL_CLAIM")
        with patch.object(s, "infer_insights", return_value={"insights": [
             {"claim": "Unsupported", "evidence_ids": ["z0001"]}] }):
            with self.assertRaises(s.AcquisitionError):
                s.analyze(cues, [], self.root, "local-model")

    def test_access_failure_is_explicit(self):
        with patch.object(s, "download_media", side_effect=s.AcquisitionError("PROVIDER_BLOCKED")):
            cues, frames, attempts, failure = s.source_evidence(
                "https://instagram.com/reel/DfOrNZxJkHI", None, None, "auto", None, self.root)
        self.assertEqual((cues, frames, failure), ([], [], "UNRESOLVED_SOURCE_ACCESS"))
        self.assertEqual(attempts[0]["status"], "PROVIDER_BLOCKED")

    def test_local_media_frames_are_kept_as_evidence_when_audio_missing(self):
        media = self.root / "demo.mp4"
        media.write_bytes(b"fixture")
        with patch.object(s, "sample_frames", return_value=[{
             "id": "f0001", "nominal_ms": 0, "file": "frame-001.jpg", "sha256": "ab"}]):
            cues, frames, attempts, failure = s.source_evidence(
                "https://instagram.com/reel/DfOrNZxJkHI", None, media, "offline", None, self.root)
        self.assertIsNone(failure)
        self.assertEqual(frames[0]["id"], "f0001")
        self.assertEqual(attempts[0]["status"], "SUCCESS")

    def test_same_input_same_receipt(self):
        _, first = self.call("--strategy", "offline", "--captions-file", str(self.captions))
        _, second = self.call("--strategy", "offline", "--captions-file", str(self.captions))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
