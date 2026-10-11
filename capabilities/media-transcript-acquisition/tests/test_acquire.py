"""Black-box CLI and mocked upstream provider canaries. Never call YouTube in CI."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("media_acquire", ROOT / "acquire.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
VTT = """WEBVTT

00:00:00.500 --> 00:00:02.000
<v Speaker>Hello &amp; welcome!</v>

00:00:02.100 --> 00:00:04.000
Vision understands screens.

00:00:04.200 --> 00:00:05.000
Vision understands screens.
"""


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.captions = self.home / "captions.vtt"
        self.captions.write_text(VTT, encoding="utf-8")
        self.output = self.home / "receipt.json"
        self.url = "https://www.youtube.com/shorts/pl0EltNU5p0"

    def cli(self, *options):
        process = subprocess.run(
            [sys.executable, str(ROOT / "acquire.py"), "--url", self.url,
             "--out", str(self.output), *options],
            capture_output=True, text=True, timeout=8, cwd=self.home
        )
        return process, json.loads(self.output.read_text(encoding="utf-8"))

    def test_offline_vtt(self):
        proc, result = self.cli("--captions-file", str(self.captions), "--strategy", "offline")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(result["source"]["video_id"], "pl0EltNU5p0")
        self.assertEqual(result["status"], "TRANSCRIPT_ACQUIRED")
        self.assertEqual(result["method"], "provided_captions")
        self.assertEqual(result["cues"][0]["text"], "Hello & welcome!")
        self.assertEqual(result["cues"][1]["end_ms"], 5000)
        self.assertEqual(len(result["cues"]), 2)

    def test_offline_srt(self):
        self.captions.write_text(
            "1\n00:00:00,000 --> 00:00:01,200\nHello\n\n"
            "2\n00:00:01,200 --> 00:00:02,300\nWorld\n", encoding="utf-8"
        )
        proc, result = self.cli("--captions-file", str(self.captions))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(result["cues"][0]["start_ms"], 0)
        self.assertEqual(len(result["cues"]), 2)

    def test_stable_and_private(self):
        _, a = self.cli("--captions-file", str(self.captions))
        _, b = self.cli("--captions-file", str(self.captions))
        self.assertEqual(a, b)
        self.assertNotIn(str(self.home), json.dumps(a))

    def test_missing_offline_source(self):
        proc, result = self.cli("--strategy", "offline")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "SOURCE_NOT_ATTACHED")
        self.assertEqual(result["proof_ceiling"], "NO_SOURCE_TEXT")

    def test_wrong_hosts_and_bad_port(self):
        for bad in ("https://youtube.com.evil.com/shorts/pl0EltNU5p0",
                    "http://youtube.com/watch?v=pl0EltNU5p0",
                    "file:///etc/passwd", "https://youtube.com/shorts/no",
                    "https://youtube.com:invalid/watch?v=pl0EltNU5p0"):
            with self.subTest(bad=bad):
                with self.assertRaises(M.AcquisitionError):
                    M.youtube_id(bad)

    def test_shorts_watch_live_share(self):
        for u in ("https://youtu.be/pl0EltNU5p0",
                  "https://m.youtube.com/watch?v=pl0EltNU5p0&t=11",
                  "https://youtube.com/live/pl0EltNU5p0", self.url):
            self.assertEqual(M.youtube_id(u), "pl0EltNU5p0")

    def test_bad_captions(self):
        self.captions.write_text("not captions", encoding="utf-8")
        proc, result = self.cli("--captions-file", str(self.captions))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "INVALID_CAPTIONS")

    def test_reversed_timestamps(self):
        with self.assertRaises(M.AcquisitionError):
            M.parse_cues("WEBVTT\n\n00:00:02.000 --> 00:00:01.000\nHi")

    def test_fallback(self):
        cues = [{"start_ms": 0, "end_ms": 1000, "text": "verified"}]
        with patch.object(M, "from_transcript_api", side_effect=M.AcquisitionError("ADAPTER_UNAVAILABLE")), patch.object(M, "from_ytdlp", return_value=(cues, "a" * 64)):
            result = M.acquire(self.url, None, "auto")
        self.assertEqual(result["method"], "yt_dlp")
        self.assertEqual([a["status"] for a in result["attempts"]], ["ADAPTER_UNAVAILABLE", "SUCCESS"])

    def test_blocked_runtime_does_not_mean_no_captions(self):
        with patch.object(M, "from_transcript_api", side_effect=M.AcquisitionError("PROVIDER_BLOCKED")), patch.object(M, "from_ytdlp", side_effect=M.AcquisitionError("ADAPTER_UNAVAILABLE")):
            result = M.acquire(self.url, None, "auto")
        self.assertEqual(result["failure"], "UNRESOLVED_SOURCE_ACCESS")
        self.assertEqual(result["cues"], [])

    def test_oversized_source(self):
        self.captions.write_bytes(b"X" * (M.MAX_BYTES + 1))
        with self.assertRaises(M.AcquisitionError):
            M.from_file(self.captions)


if __name__ == "__main__":
    unittest.main()
