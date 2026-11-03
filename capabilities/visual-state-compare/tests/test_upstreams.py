"""Offline canaries for the local upstream checkout contract."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CAP_DIR = Path(__file__).resolve().parents[1]
FILE = CAP_DIR / "upstreams.py"
SPEC = importlib.util.spec_from_file_location("vision_upstreams", FILE)
up = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(up)


class UpstreamCatalogTests(unittest.TestCase):
    def test_all_eight_pinned_sources_and_profiles(self):
        catalog = up.read_catalog(CAP_DIR / "upstreams.v1.json")
        self.assertEqual(len(catalog["upstreams"]), 8)
        self.assertEqual({i["id"] for i in up.select(catalog, "foundation")},
                         {"kornia", "paddleocr", "tesseract"})
        self.assertEqual({i["id"] for i in up.select(catalog, "ui")}, {"omniparser"})
        self.assertEqual(len(up.select(catalog, "all")), 8)

    def test_tampered_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = up.read_catalog(CAP_DIR / "upstreams.v1.json")
            catalog["upstreams"][0]["url"] = "file:///tmp/untrusted"
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(up.VisionStackError, "UNSAFE_SOURCE"):
                up.read_catalog(path)

    def test_repo_inside_checkout_is_rejected(self):
        with self.assertRaisesRegex(up.VisionStackError, "CHECKOUT_INSIDE_REPOSITORY"):
            up.safe_root(str(CAP_DIR / "private-models"))

    def test_plan_is_side_effect_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "not-created"
            result = subprocess.run(
                [sys.executable, str(FILE), "plan", "--root", str(root),
                 "--profile", "foundation"], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(root.exists())
            receipt = json.loads(result.stdout)
            self.assertTrue(all(i["status"] == "NOT_CLONED" for i in receipt["sources"]))
            self.assertFalse(receipt["engines_runtime_verified"])
            self.assertFalse(receipt["weights_installed"])

    def test_doctor_does_not_claim_a_missing_checkout_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(FILE), "doctor", "--root", tmp, "--profile", "ui"],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["sources"][0]["status"], "NOT_CLONED")

    def test_non_git_path_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = up.read_catalog(CAP_DIR / "upstreams.v1.json")
            item = up.select(catalog, "foundation")[0]
            path = Path(tmp) / item["id"]
            path.mkdir()
            marker = path / "keep.txt"
            marker.write_text("DO NOT CHANGE", encoding="utf-8")
            self.assertEqual(up.sync_one(item, Path(tmp)), "PATH_COLLISION")
            self.assertEqual(marker.read_text(encoding="utf-8"), "DO NOT CHANGE")


if __name__ == "__main__":
    unittest.main()
