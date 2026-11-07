"""Export discovery, media attach, and drive.file fallback prototypes."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.drive import classify_drive_error, publish_with_drive_file_fallback
from core.export_discovery import ExportDiscoveryError, discover_latest_export_dir
from core.media_attach import attach_drive_links_to_markdown, merge_upload_receipts
from core.transfer import run_transfer_plan

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
HOST = ROOT / "host_transfer.py"


class DiscoveryAttachPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        older = self.root / "export-20261106-100000"
        newer = self.root / "export-20261106-182436"
        older.mkdir()
        newer.mkdir()
        (older / "signal-2026-11-05-16-06-42-485.png").write_bytes(PNG)
        (newer / "signal-2026-11-05-16-06-42-485.png").write_bytes(PNG)
        (newer / "signal-2026-11-05-16-06-42-485_002.png").write_bytes(PNG)
        self.older = older
        self.newer = newer

    def test_discover_latest_timestamp(self):
        found = discover_latest_export_dir(self.root)
        self.assertEqual(found["status"], "FOUND")
        self.assertEqual(found["exportDirName"], "export-20261106-182436")
        self.assertEqual(found["imageCount"], 2)

    def test_discover_prefer_name(self):
        found = discover_latest_export_dir(self.root, prefer_name="export-20261106-100000")
        self.assertEqual(found["exportDirName"], "export-20261106-100000")

    def test_discover_prefer_missing(self):
        with self.assertRaises(ExportDiscoveryError) as ctx:
            discover_latest_export_dir(self.root, prefer_name="export-missing")
        self.assertEqual(ctx.exception.code, "EXPORT_PREFERRED_MISSING")

    def test_attach_drive_links(self):
        md = "- `signal-2026-11-05-16-06-42-485.png`\n- `missing.png`\n"
        uploads = [
            {
                "title": "signal-2026-11-05-16-06-42-485.png",
                "webViewLink": "https://drive.google.com/file/d/SYNTH/view",
            }
        ]
        result = attach_drive_links_to_markdown(md, uploads)
        self.assertEqual(result["attachedCount"], 1)
        self.assertEqual(result["missingFilenames"], ["missing.png"])
        self.assertIn("](https://drive.google.com/file/d/SYNTH/view)", result["markdown"])

    def test_merge_upload_receipts_images_map(self):
        merged = merge_upload_receipts(
            {
                "images": {
                    "a": {"title": "a.png", "webViewLink": "https://drive.google.com/file/d/A/view"},
                    "b": {"file": "b.png", "link": "https://drive.google.com/file/d/B/view"},
                }
            }
        )
        self.assertEqual(len(merged), 2)

    def test_classify_awaiting_grant(self):
        self.assertEqual(
            classify_drive_error("403 appNotAuthorizedToFile The user has not granted"),
            "AWAITING_GRANT",
        )

    def test_publish_fallback_on_reconcile_403(self):
        calls: list[tuple[str, dict]] = []

        def transport(op: str, payload):
            calls.append((op, dict(payload)))
            if op == "upload_image":
                return {
                    "title": payload["file"],
                    "webViewLink": f"https://drive.google.com/file/d/{payload['file']}/view",
                }
            if op == "upsert_doc":
                return {"id": "working-synthetic", "title": payload["title"]}
            if op == "reconcile_doc":
                raise RuntimeError("HttpError 403 appNotAuthorizedToFile")
            if op == "create_sibling_doc":
                return {"id": "sibling-synthetic", "title": payload["title"]}
            raise AssertionError(op)

        packet = {
            "bundle": {
                "docCleanMarkdown": "# Doc\n\n- `a.png`\n",
                "indexMarkdown": "# Index\n",
            },
            "plan": {
                "workingDoc": {"title": "HH Auth Guide", "semanticTarget": "working-doc"},
                "imageUploads": [{"file": "a.png", "absolutePath": "/tmp/a.png", "ordinal": 1}],
                "mediaFolderSemantic": "media-folder",
                "reconcileDocSemantic": "reconcile-doc",
                "indexDoc": None,
            },
            "profile": {"title": "HH Auth Guide", "siblingDocSemantic": "sibling-doc"},
        }
        result = publish_with_drive_file_fallback(packet, transport=transport)
        self.assertTrue(result["fallback"]["triggered"])
        self.assertEqual(result["status"], "WORKING_AND_SIBLING_SOURCE_OF_TRUTH")
        self.assertEqual(result["mediaAttach"]["attachedCount"], 1)
        ops = [c[0] for c in calls]
        self.assertIn("create_sibling_doc", ops)
        self.assertIn("reconcile_doc", ops)

    def test_transfer_plan_includes_absolute_paths(self):
        profile = json.loads(
            (ROOT / "fixtures" / "transfer-profile.synthetic.v1.json").read_text(encoding="utf-8")
        )
        selection = json.loads(
            (ROOT / "fixtures" / "selected-messages.synthetic.v1.json").read_text(encoding="utf-8")
        )
        # Need third group for expectedCount=3 with attachments on 2,3 — reuse newer + one more.
        (self.newer / "signal-2026-11-05-16-08-06-762.png").write_bytes(PNG)
        receipt = run_transfer_plan(
            profile,
            selection=selection,
            export_dir=self.newer,
            dry_run=True,
        )
        uploads = receipt["publishPlan"]["imageUploads"]
        self.assertGreaterEqual(len(uploads), 1)
        self.assertTrue(all(u.get("absolutePath") for u in uploads))

    def test_host_discover_and_publish_no_transport(self):
        discover = subprocess.run(
            [sys.executable, str(HOST), "discover-export", "--export-root", str(self.root)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(discover.returncode, 0, discover.stderr)
        found = json.loads(discover.stdout)
        self.assertEqual(found["exportDirName"], "export-20261106-182436")

        profile = ROOT / "fixtures" / "transfer-profile.synthetic.v1.json"
        selection = ROOT / "fixtures" / "selected-messages.synthetic.v1.json"
        (self.newer / "signal-2026-11-05-16-08-06-762.png").write_bytes(PNG)
        publish = subprocess.run(
            [
                sys.executable,
                str(HOST),
                "publish",
                "--profile",
                str(profile),
                "--selection",
                str(selection),
                "--export-root",
                str(self.root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(publish.returncode, 0, publish.stderr)
        receipt = json.loads(publish.stdout)
        self.assertEqual(receipt["drive"]["status"], "PLANNED_NO_TRANSPORT")
        self.assertEqual(receipt["drive"]["fallback"]["rule"], "drive.file-sibling-on-awaiting-grant")


if __name__ == "__main__":
    unittest.main()
