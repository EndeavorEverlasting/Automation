from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_canonical_path_contract_fails_closed_without_person_specific_literal(self):
        contract = json.loads(
            (ROOT / "harness/contracts/canonical-path.v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(contract["repository"], "EndeavorEverlasting/Automation")
        default = contract["profiles"]["default"]
        dev = default["development_checkout"]
        self.assertEqual(dev["literal_path"], None)
        self.assertEqual(dev["on_unresolved"], "UNKNOWN_BLOCK_NEW_CLONE")
        self.assertEqual(dev["environment_variable"], "AUTOMATION_DEV_ROOT")
        prod = default["production_use"]
        self.assertEqual(prod["default_use_state"], "UNKNOWN")
        self.assertEqual(prod["on_unresolved"], "UNKNOWN_BLOCK_PRODUCTION_MUTATION")
        self.assertIsNone(prod["repository_default_path"])
        serialized = json.dumps(contract).lower()
        self.assertNotIn("\\users\\", serialized)
        self.assertNotIn("/home/", serialized)

    def test_first_capability_has_core_adapter_and_proof_boundaries(self):
        capability = json.loads(
            (
                ROOT
                / "capabilities/playlist-link-extraction/capability.v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(capability["capability_id"], "playlist-link-extraction")
        self.assertIn("canonical JSON artifact construction", capability["core_owns"])
        self.assertIn("Playwright integration", capability["adapters_own"])
        self.assertEqual(capability["production_use_path"], "UNDECLARED")
        self.assertEqual(capability["status"], "BOUNDARY_DEFINED_IMPLEMENTATION_PENDING")

    def test_agent_contract_requires_repository_prompt_resolution(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for marker in (
            "Prompt identities are repository-owned inputs, not model-memory shortcuts.",
            "python scripts/prompt_runtime.py",
            "EXECUTE_AND_IMPLEMENT",
            "Never substitute remembered prompt text",
            "UNKNOWN_BLOCK_NEW_CLONE",
        ):
            self.assertIn(marker, agents)

    def test_contribution_policy_has_explicit_placement_lanes(self):
        policy = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for marker in (
            "capabilities/<capability-id>/",
            "adapters/<adapter-id>/",
            "Repository-wide execution/proof machinery",
            "Product-specific business logic",
            "Do not claim universal compatibility",
        ):
            self.assertIn(marker, policy)


if __name__ == "__main__":
    unittest.main()
