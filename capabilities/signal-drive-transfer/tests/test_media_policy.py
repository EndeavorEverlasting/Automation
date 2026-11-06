"""Media policy: Save-As/clipboard allowed; print-screen banned."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.media_policy import MediaPolicyError, admit_media_plan, assert_media_source_allowed


class MediaPolicyTests(unittest.TestCase):
    def test_export_and_clipboard_allowed(self):
        self.assertEqual(assert_media_source_allowed("signal-save-as-export"), "signal-save-as-export")
        self.assertEqual(assert_media_source_allowed("uia_clipboard_image"), "uia-clipboard-image")

    def test_printscreen_banned(self):
        for source in ("printscreen", "screenshot", "snip", "bitblt", "screen-capture"):
            with self.subTest(source=source):
                with self.assertRaises(MediaPolicyError) as ctx:
                    assert_media_source_allowed(source)
                self.assertEqual(ctx.exception.code, "MEDIA_SOURCE_BANNED")

    def test_plan_rejects_screenshot_action(self):
        with self.assertRaises(MediaPolicyError) as ctx:
            admit_media_plan(
                {
                    "source": "signal-save-as-export",
                    "actions": [{"kind": "printscreen"}],
                }
            )
        self.assertEqual(ctx.exception.code, "MEDIA_ACTION_BANNED")

    def test_plan_admits_export_read(self):
        admitted = admit_media_plan(
            {
                "source": "signal-save-as-export",
                "actions": [{"kind": "read-export-file"}, {"kind": "drive-upload-image"}],
            }
        )
        self.assertEqual(admitted["status"], "ADMITTED")


if __name__ == "__main__":
    unittest.main()
