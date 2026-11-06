"""Cross-platform host UI acceptance tests: no network, install or scheduler changes."""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import host_app as h

VIDEO = b"local synthetic video"
AUDIO = b"local synthetic audio"


class MediaHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make_receipt(self, mode="video"):
        expected = [("video", "video.mp4", VIDEO)]
        if mode == "audio":
            expected = [("audio", "audio.mp3", AUDIO)]
        if mode == "hybrid":
            expected.append(("audio", "audio.mp3", AUDIO))
        artifacts = []
        for role, filename, data in expected:
            (self.root / filename).write_bytes(data)
            artifacts.append({"role": role, "file": filename,
                              "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        payload = {"contract": "automation.media-artifact-delivery/v1",
                   "status": "DELIVERED", "mode": mode,
                   "artifacts": artifacts}
        receipt = self.root / "receipt.json"
        receipt.write_text(json.dumps(payload), encoding="utf-8")
        return receipt

    def test_all_modes_verify_and_hybrid_requires_both_files(self):
        for mode in ("video", "audio", "hybrid"):
            with self.subTest(mode=mode):
                receipt = self.make_receipt(mode)
                result = h.verify_receipt(receipt)
                self.assertEqual(result["status"], "VERIFIED")
                self.assertEqual(len(result["file_results"]), 2 if mode == "hybrid" else 1)

    def test_rejects_file_tampering(self):
        receipt = self.make_receipt()
        (self.root / "video.mp4").write_bytes(b"untrusted changes")
        result = h.verify_receipt(receipt)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["reason"], "FILE_INTEGRITY_MISMATCH")
        self.assertEqual(result["file_results"][0]["status"], "MISMATCH")

    def test_rejects_missing_artifact(self):
        receipt = self.make_receipt()
        (self.root / "video.mp4").unlink()
        self.assertEqual(h.verify_receipt(receipt)["status"], "FAILED")

    def test_rejects_path_traversal_in_forged_receipt(self):
        receipt = self.make_receipt()
        data = json.loads(receipt.read_text())
        data["artifacts"][0]["file"] = "../outside.mp4"
        receipt.write_text(json.dumps(data))
        result = h.verify_receipt(receipt)
        self.assertEqual(result["reason"], "INVALID_ARTIFACT_LIST")

    def test_rejects_false_success_or_bad_roles(self):
        receipt = self.make_receipt("hybrid")
        data = json.loads(receipt.read_text())
        data["artifacts"] = data["artifacts"][:1]
        receipt.write_text(json.dumps(data))
        self.assertEqual(h.verify_receipt(receipt)["reason"], "INVALID_ARTIFACT_LIST")
        receipt = self.make_receipt()
        data = json.loads(receipt.read_text())
        data["artifacts"][0]["role"] = "audio"
        receipt.write_text(json.dumps(data))
        self.assertEqual(h.verify_receipt(receipt)["reason"], "INVALID_ARTIFACT_LIST")

    def test_failure_receipt_never_verifies(self):
        receipt = self.make_receipt()
        data = json.loads(receipt.read_text())
        data["status"] = "BLOCKED"
        receipt.write_text(json.dumps(data))
        self.assertEqual(h.verify_receipt(receipt)["reason"], "NOT_A_DELIVERY")

    def test_malformed_missing_or_large_receipt(self):
        receipt = self.root / "receipt.json"
        self.assertEqual(h.verify_receipt(receipt)["reason"], "INVALID_RECEIPT")
        receipt.write_bytes(b"garbled {}")
        self.assertEqual(h.verify_receipt(receipt)["status"], "FAILED")
        receipt.write_bytes(b"x" * 64001)
        self.assertEqual(h.verify_receipt(receipt)["reason"], "INVALID_RECEIPT")

    def test_no_inference_of_content_authenticity(self):
        receipt = self.make_receipt()
        result = h.verify_receipt(receipt)
        self.assertEqual(result["proof_ceiling"], "LOCAL_FILE_INTEGRITY_ONLY")

    def test_rejects_symlink_artifact_if_available(self):
        receipt = self.make_receipt()
        media = self.root / "video.mp4"
        replacement = self.root / "target.mp4"
        media.rename(replacement)
        try:
            media.symlink_to(replacement)
        except (OSError, NotImplementedError):
            self.skipTest("Host does not permit user symlinks")
        self.assertEqual(h.verify_receipt(receipt)["status"], "FAILED")

    def test_doctor_defers_when_tools_absent(self):
        with patch.object(h.shutil, "which", return_value=None):
            info = h.doctor()
        self.assertEqual(info["ready_modes"], [])
        self.assertFalse(info["yt_dlp"]["available"])

    def test_doctor_video_only_without_ffmpeg(self):
        with patch.object(h.shutil, "which", side_effect=lambda name: "/test/ytdlp" if name == "yt-dlp" else None), \
             patch.object(h, "tool_version", return_value="2026.10.01"):
            info = h.doctor()
        self.assertEqual(info["ready_modes"], ["video"])
        self.assertFalse(info["ffmpeg"]["available"])

    def test_doctor_both_tools_support_all_modes(self):
        with patch.object(h.shutil, "which", side_effect=lambda name: "/test/" + name), \
             patch.object(h, "tool_version", return_value="test-version"):
            info = h.doctor()
        self.assertEqual(info["ready_modes"], ["video", "audio", "hybrid"])

    def test_doctor_cannot_run_tools_with_shell(self):
        with patch.object(h.subprocess, "run", return_value=subprocess.CompletedProcess(
                args=["yt-dlp"], returncode=0, stdout=b"version\n")) as run:
            self.assertEqual(h.tool_version(["yt-dlp", "--version"]), "version")
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertIs(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(run.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_capture_preserves_existing_engine_and_receipt(self):
        packet = {"status": "DELIVERED", "failure": None,
                  "artifacts": [{"role": "video", "file": "video.mp4", "sha256": "a" * 64, "bytes": 99}]}
        out = io.StringIO()
        with patch.object(h, "capture", return_value=(packet, self.root / "receipt.json")) as stub, redirect_stdout(out):
            code = h.do_capture("https://youtu.be/pl0EltNU5p0", "video", self.root, 500, 300)
        self.assertEqual(code, 0)
        stub.assert_called_once()
        self.assertEqual(json.loads(out.getvalue())["status"], "DELIVERED")

    def test_local_filesystem_error_has_typed_result(self):
        out = io.StringIO()
        with patch.object(h, "capture", side_effect=PermissionError("private-user-directory")), redirect_stdout(out):
            code = h.do_capture("https://youtu.be/pl0EltNU5p0", "video", self.root, 500, 300)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["failure"], "LOCAL_IO_ERROR")
        self.assertNotIn("private-user-directory", out.getvalue())

    def test_cli_verify_is_independent_host_process(self):
        receipt = self.make_receipt("hybrid")
        p = subprocess.run([sys.executable, str(ROOT / "host_app.py"), "verify", "--receipt", str(receipt)],
                           capture_output=True, text=True, cwd=self.root, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["status"], "VERIFIED")

    def test_cli_doctor_is_read_only_and_machine_readable(self):
        p = subprocess.run([sys.executable, str(ROOT / "host_app.py"), "doctor", "--json"],
                           capture_output=True, text=True, cwd=self.root, timeout=12)
        self.assertIn(p.returncode, (0, 2))
        info = json.loads(p.stdout)
        self.assertEqual(info["contract"], "automation.media-host/v1")
        self.assertIn(info["platform"], ("linux", "windows", "darwin"))
        self.assertFalse(list(self.root.iterdir()))

    def test_platform_launchers_are_thin_and_explicit(self):
        win = (ROOT / "Run-Media-Delivery.cmd").read_text()
        mint = (ROOT / "run-media-delivery.sh").read_text()
        self.assertIn("%~dp0host_app.py", win)
        self.assertIn("%*", win)
        self.assertIn("host_app.py", mint)
        self.assertIn('"$@"', mint)
        self.assertNotIn("schtasks /create", win.lower())
        self.assertNotIn("crontab", mint.lower())
        self.assertNotIn("curl ", mint.lower())


if __name__ == "__main__":
    unittest.main()
