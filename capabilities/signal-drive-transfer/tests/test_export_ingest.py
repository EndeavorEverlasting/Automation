"""Export ingest prototypes for Signal Save-As folders."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.export_ingest import ExportIngestError, ingest_export_dir, merge_selection_with_export_media

# 1x1 PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


class ExportIngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.export = Path(self.temp.name) / "export"
        self.export.mkdir()

    def _write_signal_group(self, stem: str, count: int) -> None:
        (self.export / f"{stem}.png").write_bytes(PNG)
        for seq in range(2, count + 1):
            (self.export / f"{stem}_{seq:03d}.png").write_bytes(PNG)

    def test_groups_flat_signal_save_as_images(self):
        self._write_signal_group("signal-2026-11-05-16-06-42-485", 3)
        self._write_signal_group("signal-2026-11-05-16-08-06-762", 2)
        result = ingest_export_dir(self.export, expected_media_groups=2)
        self.assertEqual(result["ingestMode"], "signal-flat-images")
        self.assertEqual(result["selectedCount"], 2)
        self.assertEqual(result["attachmentCount"], 5)
        self.assertEqual(len(result["messages"][0]["attachmentsSaved"]), 3)
        self.assertEqual(result["source"], "signal-save-as-export")

    def test_merge_selection_with_export_media(self):
        self._write_signal_group("signal-2026-11-05-16-06-42-485", 2)
        self._write_signal_group("signal-2026-11-05-16-08-06-762", 1)
        exported = ingest_export_dir(self.export)["messages"]
        selection = json.loads(
            (ROOT / "fixtures" / "selected-messages.synthetic.v1.json").read_text(encoding="utf-8")
        )["messages"]
        merged = merge_selection_with_export_media(selection, exported)
        self.assertEqual(len(merged), 3)
        self.assertFalse(merged[0].get("hasAttachments"))
        self.assertEqual(len(merged[1]["attachmentsSaved"]), 2)
        self.assertEqual(len(merged[2]["attachmentsSaved"]), 1)
        self.assertIn("Synthetic plan", merged[1]["body"])

    def test_media_group_count_mismatch_fails(self):
        self._write_signal_group("signal-2026-11-05-16-06-42-485", 1)
        with self.assertRaises(ExportIngestError) as ctx:
            ingest_export_dir(self.export, expected_media_groups=2)
        self.assertEqual(ctx.exception.code, "EXPORT_MEDIA_GROUP_COUNT")


if __name__ == "__main__":
    unittest.main()
