"""Transfer orchestration call-stack prototypes."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.match import match_messages
from core.media_policy import MediaPolicyError
from core.transfer import run_transfer_plan

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


class TransferPlanTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = ROOT / "fixtures"
        self.profile = json.loads(
            (self.fixtures / "transfer-profile.synthetic.v1.json").read_text(encoding="utf-8")
        )
        self.selection = json.loads(
            (self.fixtures / "selected-messages.synthetic.v1.json").read_text(encoding="utf-8")
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.export = Path(self.temp.name) / "export"
        self.export.mkdir()
        (self.export / "signal-2026-11-05-16-06-42-485.png").write_bytes(PNG)
        (self.export / "signal-2026-11-05-16-06-42-485_002.png").write_bytes(PNG)
        (self.export / "signal-2026-11-05-16-08-06-762.png").write_bytes(PNG)

    def test_selection_plus_export_dry_run(self):
        receipt = run_transfer_plan(
            self.profile,
            selection=self.selection,
            export_dir=self.export,
            dry_run=True,
        )
        self.assertEqual(receipt["status"], "PLANNED")
        self.assertEqual(receipt["selectedCount"], 3)
        self.assertEqual(receipt["document"]["imageUploadCount"], 3)
        self.assertEqual(receipt["source"], "selection+signal-save-as-export")
        self.assertIn("banned", receipt["publishPlan"]["mediaPolicy"])

    def test_db_match_stack(self):
        rows = json.loads((self.fixtures / "db-rows.synthetic.v1.json").read_text(encoding="utf-8"))
        match_profile = json.loads(
            (self.fixtures / "match-profile.synthetic.v1.json").read_text(encoding="utf-8")
        )
        matched = match_messages(rows, match_profile, expected_count=3)
        self.assertEqual(matched["selectedCount"], 3)
        self.assertEqual([m["id"] for m in matched["messages"]], ["row-1", "row-2", "row-3"])

    def test_printscreen_profile_rejected(self):
        bad = dict(self.profile)
        bad["mediaSource"] = "printscreen"
        with self.assertRaises(MediaPolicyError):
            run_transfer_plan(bad, selection=self.selection, export_dir=self.export, dry_run=True)


if __name__ == "__main__":
    unittest.main()
