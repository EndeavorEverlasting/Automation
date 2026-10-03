from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "harness/contracts/idea-work-continuity.v1.json"
EXAMPLE_PATH = ROOT / "docs/examples/idea-work-continuity.tokencorridor-deferred.v1.json"
VALIDATOR_PATH = ROOT / "scripts/validate_idea_work_continuity.py"

SPEC = importlib.util.spec_from_file_location("validate_idea_work_continuity", VALIDATOR_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class IdeaWorkContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    def validate(self, payload: dict) -> list[str]:
        return MOD.validate_receipt(payload, self.contract)

    def test_tokencorridor_deferred_adoption_example_passes(self) -> None:
        self.assertEqual(self.validate(copy.deepcopy(self.example)), [])

    def test_execution_relevant_chat_only_equivalent_fails(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["durable_anchor"] = {"type": "NO_ACTION", "identity": "chat-only"}
        errors = self.validate(payload)
        self.assertTrue(any("durable non-NO_ACTION anchor" in error for error in errors))

    def test_existing_plan_cannot_create_competing_plan(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["target"]["consumer_state"] = "STABLE"
        payload["target"]["collision_state"] = "CLEAR"
        payload["disposition"] = "CREATE_REMOTE_PLAN"
        payload["durable_anchor"] = {
            "type": "NEW_PLAN",
            "identity": "docs/plans/competing-plan.md",
        }
        errors = self.validate(payload)
        self.assertTrue(
            any("existing canonical plan is FOUND" in error for error in errors)
        )

    def test_migration_active_non_clear_collision_must_defer(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["disposition"] = "APPEND_ITERATION"
        payload["durable_anchor"] = {
            "type": "PLAN_ITERATION",
            "identity": "consumer-plan#new-iteration",
        }
        errors = self.validate(payload)
        self.assertTrue(
            any("must use DEFERRED_ADOPTION" in error for error in errors)
        )

    def test_priority_cannot_be_inferred(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["priority"] = {"source": "UNSPECIFIED", "value": "HIGH"}
        errors = self.validate(payload)
        self.assertIn("UNSPECIFIED priority must have value=null", errors)

    def test_private_provider_url_is_rejected(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["source"]["item_identity_handle"] = (
            "https://docs.google.com/spreadsheets/d/private"
        )
        errors = self.validate(payload)
        self.assertTrue(any("privacy violation" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
