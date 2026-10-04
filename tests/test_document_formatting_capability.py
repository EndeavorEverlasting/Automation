from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "capabilities" / "document-formatting" / "core" / "contract.py"
SPEC = importlib.util.spec_from_file_location("document_formatting_contract_test", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)

FIXTURE = (
    ROOT
    / "capabilities"
    / "document-formatting"
    / "fixtures"
    / "consumer-profile.synthetic.v1.json"
)


class DocumentFormattingCapabilityTests(unittest.TestCase):
    def load_fixture(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_synthetic_consumer_profile_builds_portable_plan(self):
        profile = self.load_fixture()
        self.assertEqual([], MOD.validate_profile(profile))
        plan = MOD.build_plan(profile)

        self.assertEqual("document-formatting-plan/v1", plan["schema_version"])
        self.assertEqual("document-formatting", plan["capability_id"])
        self.assertEqual(profile["consumer_id"], plan["consumer_id"])
        self.assertEqual(64, len(plan["profile_sha256"]))
        self.assertTrue(plan["prevent_proof_promotion"])

        stages = {item["stage_id"]: item for item in plan["stages"]}
        self.assertIn("APPLY_PROVIDER::native-docs-provider", stages)
        self.assertIn("READBACK_PROVIDER::native-docs-provider", stages)
        self.assertIn("VISUAL_ACCEPTANCE::native-docs-render", stages)
        self.assertIn("VISUAL_ACCEPTANCE::desktop-editor-render", stages)
        self.assertIn("CROSS_SURFACE_FIDELITY", stages)
        self.assertIn("LOCK_NON_COLOR_MECHANICS", stages)
        self.assertIn("APPLY_BRAND_OVERLAY", stages)

        self.assertEqual(
            ["APPLY_BRAND_OVERLAY"],
            plan["terminal_dependencies"],
        )

    def test_branding_fails_closed_without_non_color_lock(self):
        profile = self.load_fixture()
        profile["proof_policy"]["lock_non_color_before_branding"] = False
        errors = MOD.validate_profile(profile)
        self.assertIn(
            "branding requires proof_policy.lock_non_color_before_branding=true",
            errors,
        )

    def test_surface_provider_must_exist(self):
        profile = self.load_fixture()
        profile["visual_surfaces"][0]["provider_id"] = "missing-provider"
        errors = MOD.validate_profile(profile)
        self.assertTrue(
            any("provider_id must reference provider_adapters" in item for item in errors)
        )

    def test_core_has_no_consumer_specific_hh_assumption(self):
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        forbidden = ("nyc health", "hospitals", "northwell", "hh-metropolitan")
        self.assertFalse(any(item in source for item in forbidden), source)


if __name__ == "__main__":
    unittest.main()
