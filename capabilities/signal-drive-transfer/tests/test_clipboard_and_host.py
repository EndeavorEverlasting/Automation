"""Clipboard seam + host CLI prototypes."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.clipboard_media import execute_clipboard_copy, plan_clipboard_copy_for_message
from core.media_policy import MediaPolicyError

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
HOST = ROOT / "host_transfer.py"


class ClipboardAndHostTests(unittest.TestCase):
    def test_clipboard_plan_and_execute(self):
        plan = plan_clipboard_copy_for_message(ordinal=4, attachment_index=0)
        self.assertEqual(plan["source"], "uia-clipboard-image")
        focused = {}

        def uia_focus(ordinal, attachment_index):
            focused["o"] = ordinal
            focused["i"] = attachment_index

        result = execute_clipboard_copy(
            plan,
            uia_focus=uia_focus,
            clipboard_copy=lambda: None,
            clipboard_read_image=lambda: PNG,
        )
        self.assertEqual(result["status"], "COPIED")
        self.assertEqual(focused, {"o": 4, "i": 0})

    def test_clipboard_rejects_non_image(self):
        plan = plan_clipboard_copy_for_message(ordinal=1)
        with self.assertRaises(MediaPolicyError):
            execute_clipboard_copy(
                plan,
                uia_focus=lambda *_: None,
                clipboard_copy=lambda: None,
                clipboard_read_image=lambda: b"not-an-image",
            )

    def test_host_doctor_and_admit_media(self):
        doctor = subprocess.run(
            [sys.executable, str(HOST), "doctor"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        payload = json.loads(doctor.stdout)
        self.assertIn("printscreen", payload["mediaBanned"])

        banned = subprocess.run(
            [sys.executable, str(HOST), "admit-media", "--source", "screenshot", "--action", "read-export-file"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(banned.returncode, 0)

    def test_host_ingest_real_shape_synthetic_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            export = Path(tmp) / "export"
            export.mkdir()
            (export / "signal-2026-11-05-16-06-42-485.png").write_bytes(PNG)
            (export / "signal-2026-11-05-16-06-42-485_002.png").write_bytes(PNG)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(HOST),
                    "ingest-export",
                    "--export-dir",
                    str(export),
                    "--expected-media-groups",
                    "1",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["attachmentCount"], 2)


if __name__ == "__main__":
    unittest.main()
