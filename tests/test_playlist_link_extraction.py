from __future__ import annotations

import csv
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_DIR = ROOT / "capabilities/playlist-link-extraction"
FIXTURE_PATH = CAPABILITY_DIR / "fixtures/synthetic-observation-batch.v1.json"
CLI_PATH = CAPABILITY_DIR / "extract_links.py"


def load_core_module():
    capability_path = str(CAPABILITY_DIR)
    if capability_path not in sys.path:
        sys.path.insert(0, capability_path)
    return importlib.import_module("core")


class PlaylistLinkExtractionCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.core = load_core_module()
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_capability_status_advances_to_core_implemented(self) -> None:
        capability = json.loads(
            (CAPABILITY_DIR / "capability.v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(capability["status"], "CORE_IMPLEMENTED_ADAPTERS_PENDING")
        self.assertEqual(
            capability["entrypoint"],
            "capabilities/playlist-link-extraction/extract_links.py",
        )
        self.assertTrue((CAPABILITY_DIR / "schemas/observation-batch.v1.json").is_file())
        self.assertTrue((CAPABILITY_DIR / "schemas/artifact.v1.json").is_file())

    def test_url_normalization_is_provider_agnostic(self) -> None:
        normalized = self.core.normalize_url(
            "HTTPS://Example.TEST:443/video/1?b=2&a=1#frag"
        )
        self.assertEqual(normalized, "https://example.test/video/1?a=1&b=2")

    def test_build_artifact_separates_occurrences_from_unique_links(self) -> None:
        artifact = self.core.build_artifact(self.fixture)
        self.assertEqual(artifact["schema_version"], "playlist-link-artifact/v1")
        self.assertEqual(artifact["capability_id"], "playlist-link-extraction")
        self.assertEqual(len(artifact["occurrences"]), 4)
        self.assertEqual(len(artifact["unique_links"]), 2)
        self.assertEqual(artifact["receipt"]["occurrence_count"], 4)
        self.assertEqual(artifact["receipt"]["unique_link_count"], 2)

        first_unique = artifact["unique_links"][0]
        self.assertEqual(
            first_unique["normalized_url"],
            "https://example.test/video/1?a=1&b=2",
        )
        self.assertEqual(first_unique["occurrence_count"], 2)

        second_unique = artifact["unique_links"][1]
        self.assertEqual(second_unique["normalized_url"], "https://example.test/video/2")
        self.assertEqual(second_unique["occurrence_count"], 2)
        self.assertEqual(second_unique["first_target_id"], "target-a")

    def test_csv_projection_is_derived_from_canonical_json(self) -> None:
        artifact = self.core.build_artifact(self.fixture)
        rows = self.core.artifact_to_csv_rows(artifact)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["normalized_url"], "https://example.test/video/1?a=1&b=2")

    def test_unknown_target_id_fails_closed(self) -> None:
        bad = json.loads(json.dumps(self.fixture))
        bad["observations"][0]["target_id"] = "missing-target"
        errors = self.core.validate_observation_batch(bad)
        self.assertTrue(any("not declared in targets" in error for error in errors))

    def test_malformed_observation_url_fails_closed_during_validate(self) -> None:
        bad = json.loads(json.dumps(self.fixture))
        bad["observations"][0]["url"] = "not-a-url"
        errors = self.core.validate_observation_batch(bad)
        self.assertTrue(any("url is invalid" in error for error in errors))

    def test_cli_builds_json_and_csv_from_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_json = Path(tmp) / "artifact.json"
            out_csv = Path(tmp) / "artifact.csv"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--batch",
                    str(FIXTURE_PATH),
                    "--output-json",
                    str(out_json),
                    "--output-csv",
                    str(out_csv),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            artifact = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(artifact["receipt"]["unique_link_count"], 2)
            with out_csv.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                csv_rows = list(reader)
            self.assertEqual(len(csv_rows), 4)

    def test_root_wayfinding_exposes_capability_entrypoint(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("playlist-link-extraction", readme)
        self.assertIn("extract_links.py", readme)
        self.assertIn("CORE_IMPLEMENTED_ADAPTERS_PENDING", readme)

    def test_adapters_directory_does_not_claim_live_provider(self) -> None:
        adapter_readme = (CAPABILITY_DIR / "adapters/README.md").read_text(encoding="utf-8")
        self.assertIn("No live provider adapter is admitted", adapter_readme)
        live_dirs = [
            path
            for path in (CAPABILITY_DIR / "adapters").iterdir()
            if path.is_dir()
        ]
        self.assertEqual(live_dirs, [])


if __name__ == "__main__":
    unittest.main()
