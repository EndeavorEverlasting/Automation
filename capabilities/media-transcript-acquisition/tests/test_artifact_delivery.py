"""Offline acceptance canaries for host media artifact delivery. No network access."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import deliver_artifact as d


class ArtifactDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "private-output"
        self.url = "https://www.instagram.com/reel/DfOrNZxJkHI/?utm_source=tracker"

    def runner(self, argv, **kwargs):
        self.assertFalse(kwargs["shell"])
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)
        self.assertIn("--ignore-config", argv)
        self.assertIn("--no-playlist", argv)
        self.assertIn("--no-remote-components", argv)
        self.assertNotIn("utm_source", " ".join(argv))
        if argv[0] == "/test/ffmpeg":
            Path(argv[-1]).write_bytes(b"synthetic audio")
        else:
            path = Path(argv[argv.index("-o") + 1])
            suffix = "mp3" if "-x" in argv else "mp4"
            Path(str(path).replace("%(ext)s", suffix)).write_bytes(b"synthetic video-or-audio")
        return subprocess.CompletedProcess(argv, 0)

    def which(self, name):
        return "/test/" + name

    def test_video_written_and_hash_verified(self):
        with patch.object(d.shutil, "which", side_effect=self.which), \
             patch.object(d.subprocess, "run", side_effect=self.runner):
            packet, receipt = d.capture(self.url, "video", self.out)
        self.assertEqual(packet["status"], "DELIVERED")
        self.assertEqual(packet["mode"], "video")
        self.assertEqual(packet["source"]["url"], "https://www.instagram.com/reel/DfOrNZxJkHI")
        self.assertEqual([a["role"] for a in packet["artifacts"]], ["video"])
        video = receipt.parent / "video.mp4"
        self.assertTrue(video.is_file())
        self.assertEqual(packet["artifacts"][0]["sha256"], hashlib.sha256(video.read_bytes()).hexdigest())
        self.assertEqual(packet, json.loads(receipt.read_text()))
        self.assertEqual(sorted(p.name for p in receipt.parent.iterdir()), ["receipt.json", "video.mp4"])
        self.assertNotIn("utm_source", receipt.read_text())

    def test_audio_and_hybrid_have_independent_verified_artifacts(self):
        for mode in ("audio", "hybrid"):
            with self.subTest(mode=mode), \
                 patch.object(d.shutil, "which", side_effect=self.which), \
                 patch.object(d.subprocess, "run", side_effect=self.runner):
                packet, receipt = d.capture("https://youtu.be/pl0EltNU5p0", mode, self.out)
            self.assertEqual(packet["status"], "DELIVERED")
            self.assertEqual([item["role"] for item in packet["artifacts"]],
                             ["audio"] if mode == "audio" else ["video", "audio"])
            self.assertTrue((receipt.parent / "audio.mp3").is_file())

    def test_unavailable_adapter_produces_blocked_receipt(self):
        with patch.object(d.shutil, "which", return_value=None):
            packet, receipt = d.capture(self.url, "video", self.out)
        self.assertEqual(packet["failure"], "YTDLP_UNAVAILABLE")
        self.assertEqual(packet["artifacts"], [])
        self.assertEqual(json.loads(receipt.read_text()), packet)
        self.assertEqual(len(list(self.out.glob(".media-acquire-*"))), 0)

    def test_ffmpeg_required_for_audio_or_hybrid(self):
        with patch.object(d.shutil, "which", side_effect=lambda name:
                          "/test/yt-dlp" if name == "yt-dlp" else None):
            packet, receipt = d.capture(self.url, "hybrid", self.out)
        self.assertEqual(packet["failure"], "FFMPEG_UNAVAILABLE")
        self.assertTrue(receipt.exists())

    def test_provider_failure_cleans_staging_and_redacts_tool_output(self):
        def deny(argv, **kwargs):
            self.assertFalse(kwargs["shell"])
            return subprocess.CompletedProcess(argv, 1, stderr=b"PRIVATE TOKEN")
        with patch.object(d.shutil, "which", side_effect=self.which), \
             patch.object(d.subprocess, "run", side_effect=deny):
            packet, receipt = d.capture(self.url, "video", self.out)
        self.assertEqual(packet["failure"], "PROVIDER_OR_PROCESS_ERROR")
        self.assertNotIn("PRIVATE TOKEN", receipt.read_text())
        self.assertFalse(list(self.out.glob(".media-acquire-*")))

    def test_invalid_input_and_output_git_boundary(self):
        bad = ["http://youtube.com/watch?v=pl0EltNU5p0",
               "https://youtube.com.evil.org/watch?v=pl0EltNU5p0",
               "https://user:secret@youtube.com/watch?v=pl0EltNU5p0",
               "https://localhost/secret"]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(d.DeliveryError):
                d.capture(url, "video", self.out)
        with self.assertRaisesRegex(d.DeliveryError, "OUTPUT_INSIDE_REPOSITORY"):
            d.capture(self.url, "video", ROOT / "Outputs")
        with self.assertRaisesRegex(d.DeliveryError, "INVALID_LIMIT"):
            d.capture(self.url, "video", self.out, max_mb=5000)

    def test_oversize_and_empty_payload_fail_closed(self):
        for payload, expected in ((b"", "EMPTY_ARTIFACT"), (b"x" * 1024 * 1024 * 2, "ARTIFACT_TOO_LARGE")):
            def runner(argv, **kwargs):
                path = Path(argv[argv.index("-o") + 1].replace("%(ext)s", "mp4"))
                path.write_bytes(payload)
                return subprocess.CompletedProcess(argv, 0)
            with self.subTest(status=expected), \
                 patch.object(d.shutil, "which", side_effect=self.which), \
                 patch.object(d.subprocess, "run", side_effect=runner):
                packet, receipt = d.capture(self.url, "video", self.out, max_mb=1)
            self.assertEqual(packet["failure"], expected)
            self.assertTrue(receipt.is_file())
            self.assertEqual(list(self.out.glob("media-*")), [])

    @unittest.skipIf(os.name == "nt", "POSIX standalone consumer canary")
    def test_isolated_cli_consumer_using_fake_host_tool(self):
        # A normal consumer uses only the documented CLI: no imports, no network.
        fakebin = Path(self.temp.name) / "bin"
        fakebin.mkdir()
        binary = fakebin / "yt-dlp"
        binary.write_text(
            "#!/usr/bin/env python3\n"
            "import sys,pathlib\n"
            "a=sys.argv; p=a[a.index('-o')+1].replace('%(ext)s','mp4')\n"
            "pathlib.Path(p).write_bytes(b'fixture-media')\n", encoding="utf-8")
        binary.chmod(0o700)
        env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ.get("PATH", ""))
        command = [sys.executable, str(ROOT / "deliver_artifact.py"),
                   "--url", "https://www.youtube.com/shorts/pl0EltNU5p0",
                   "--mode", "video", "--output-dir", str(self.out)]
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        info = json.loads(result.stdout)
        self.assertEqual(info["status"], "DELIVERED")
        receipt = json.loads(Path(info["receipt"]).read_text())
        self.assertEqual(receipt["artifacts"][0]["bytes"], len(b"fixture-media"))


if __name__ == "__main__":
    unittest.main()
