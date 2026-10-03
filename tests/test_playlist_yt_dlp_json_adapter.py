from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_DIR = ROOT / "capabilities/playlist-link-extraction"
ADAPTER_DIR = CAPABILITY_DIR / "adapters/yt-dlp-json"
FIXTURE_PATH = ADAPTER_DIR / "fixtures/sample-playlist.v1.json"
ADAPTER_CLI = ADAPTER_DIR / "adapt.py"
CORE_CLI = CAPABILITY_DIR / "extract_links.py"


def load_adapter_module():
    adapter_path = str(ADAPTER_DIR)
    if adapter_path not in sys.path:
        sys.path.insert(0, adapter_path)
    return importlib.import_module("convert")


def load_core_module():
    capability_path = str(CAPABILITY_DIR)
    if capability_path not in sys.path:
        sys.path.insert(0, capability_path)
    return importlib.import_module("core")


class YtDlpJsonAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = load_adapter_module()
        cls.core = load_core_module()
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_adapter_surface_is_discoverable(self) -> None:
        self.assertTrue(ADAPTER_CLI.is_file())
        self.assertTrue((ADAPTER_DIR / "README.md").is_file())
        self.assertTrue(
            (ADAPTER_DIR / "schemas/provider-payload.v1.json").is_file()
        )
        capability = json.loads(
            (CAPABILITY_DIR / "capability.v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(capability["status"], "CORE_IMPLEMENTED_ADAPTERS_PENDING")
        self.assertIn("yt-dlp-json", capability.get("adapters", {}))

    def test_valid_payload_preserves_order_and_repeats(self) -> None:
        batch = self.adapter.convert_playlist_payload(
            self.fixture,
            target_id="target-a",
        )
        self.assertEqual(batch["schema_version"], "playlist-link-observation-batch/v1")
        self.assertEqual(len(batch["observations"]), 4)
        ordinals = [item["ordinal"] for item in batch["observations"]]
        self.assertEqual(ordinals, [0, 1, 2, 3])
        urls = [item["url"] for item in batch["observations"]]
        self.assertEqual(
            urls,
            [
                "HTTPS://Example.TEST:443/video/1?b=2&a=1#frag",
                "https://example.test/video/2",
                "https://example.test/video/1?a=1&b=2",
                "https://example.test/video/2",
            ],
        )
        self.assertTrue(all(item["adapter_id"] == "yt-dlp-json" for item in batch["observations"]))
        self.assertEqual(
            batch["targets"][0]["source_ref"],
            "https://example.test/playlist/PLSYNTHETIC001",
        )

    def test_null_entries_are_skipped_without_consuming_ordinals(self) -> None:
        batch = self.adapter.convert_playlist_payload(
            self.fixture,
            target_id="target-a",
        )
        self.assertEqual(len(batch["observations"]), 4)
        self.assertEqual(batch["observations"][2]["title"], "First item repeated")

    def test_malformed_payload_fails_closed(self) -> None:
        errors = self.adapter.validate_provider_payload({"_type": "video", "entries": []})
        self.assertTrue(any("_type" in error for error in errors))
        self.assertTrue(any("non-empty list" in error for error in errors))

    def test_entries_without_urls_fail_closed(self) -> None:
        payload = {
            "_type": "playlist",
            "entries": [{"id": "no-url", "title": "Missing URL"}],
        }
        errors = self.adapter.validate_provider_payload(payload)
        self.assertTrue(any("usable URL-bearing" in error for error in errors))

    def test_secret_bearing_keys_fail_closed(self) -> None:
        payload = {
            "_type": "playlist",
            "entries": [
                {
                    "id": "vid",
                    "webpage_url": "https://example.test/video/1",
                    "cookie": "session=forbidden",
                }
            ],
        }
        errors = self.adapter.validate_provider_payload(payload)
        self.assertTrue(any("forbidden" in error for error in errors))

    def test_adapter_then_core_parity_matches_established_semantics(self) -> None:
        batch = self.adapter.convert_playlist_payload(
            self.fixture,
            target_id="target-a",
        )
        artifact = self.core.build_artifact(batch)
        self.assertEqual(artifact["receipt"]["occurrence_count"], 4)
        self.assertEqual(artifact["receipt"]["unique_link_count"], 2)
        self.assertEqual(
            artifact["unique_links"][0]["normalized_url"],
            "https://example.test/video/1?a=1&b=2",
        )
        self.assertEqual(artifact["unique_links"][0]["occurrence_count"], 2)
        self.assertEqual(
            artifact["unique_links"][1]["normalized_url"],
            "https://example.test/video/2",
        )
        self.assertEqual(artifact["unique_links"][1]["occurrence_count"], 2)
        self.assertIn("yt-dlp-json", artifact["receipt"]["adapter_ids"])

    def test_cli_chain_emits_observation_batch_and_core_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch_path = Path(tmp) / "batch.json"
            artifact_path = Path(tmp) / "artifact.json"
            adapt = subprocess.run(
                [
                    sys.executable,
                    str(ADAPTER_CLI),
                    "--payload",
                    str(FIXTURE_PATH),
                    "--target-id",
                    "target-a",
                    "--output-batch",
                    str(batch_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(adapt.returncode, 0, adapt.stderr)
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            self.assertEqual(len(batch["observations"]), 4)

            core = subprocess.run(
                [
                    sys.executable,
                    str(CORE_CLI),
                    "--batch",
                    str(batch_path),
                    "--output-json",
                    str(artifact_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(core.returncode, 0, core.stderr)
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["receipt"]["unique_link_count"], 2)

    def test_docs_state_offline_adapter_proof_ceiling(self) -> None:
        adapter_readme = (ADAPTER_DIR / "README.md").read_text(encoding="utf-8")
        parent_readme = (CAPABILITY_DIR / "adapters/README.md").read_text(encoding="utf-8")
        capability_md = (CAPABILITY_DIR / "CAPABILITY.md").read_text(encoding="utf-8")
        self.assertIn("offline", adapter_readme.lower())
        self.assertIn("yt-dlp-json", parent_readme)
        self.assertIn("Live `yt-dlp` execution", capability_md)
        self.assertIn("CORE_IMPLEMENTED_ADAPTERS_PENDING", capability_md)


if __name__ == "__main__":
    unittest.main()
