from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING_CONTRACT = ROOT / "capabilities/artifact-sync/schemas/binding.v1.json"
BINDING_EXAMPLE = ROOT / "capabilities/artifact-sync/fixtures/binding.example.v1.json"
VALIDATOR = ROOT / "scripts/validate_artifact_sync_binding.py"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validator_module():
    spec = importlib.util.spec_from_file_location("binding_validator", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArtifactSyncReviewRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load(BINDING_CONTRACT)
        cls.validator = validator_module()

    def test_rejects_url_shaped_provider_handle(self):
        binding = load(BINDING_EXAMPLE)
        binding["provider"]["locator_handle"] = "scheme" + "://opaque"
        errors = self.validator.validate_binding(binding, self.contract)
        self.assertTrue(any("URL or absolute path" in error for error in errors))

    def test_rejects_absolute_baseline_handle(self):
        binding = load(BINDING_EXAMPLE)
        binding["baseline_state"]["state_handle"] = chr(47) + "tmp/artifact-state"
        errors = self.validator.validate_binding(binding, self.contract)
        self.assertTrue(any("URL or absolute path" in error for error in errors))

    def test_native_artifact_requires_provider_native_write(self):
        binding = load(BINDING_EXAMPLE)
        binding["sync_policy"]["native_write_policy"] = "raw_bytes_allowed_for_blob_only"
        errors = self.validator.validate_binding(binding, self.contract)
        self.assertTrue(any("native artifact kinds require" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
