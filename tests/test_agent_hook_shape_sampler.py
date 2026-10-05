from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "capabilities" / "agent-hook-runtime"


def _load_sampler_modules() -> tuple[Any, Any]:
    """Import the sampler package without leaving `core` on sys.path/sys.modules.

    Several capabilities expose a top-level `core` package, so this test must not
    change interpreter-global import state or it silently shadows them.
    """
    displaced = {
        name: module
        for name, module in list(sys.modules.items())
        if name == "core" or name.startswith("core.")
    }
    for name in displaced:
        del sys.modules[name]
    saved_path = list(sys.path)
    sys.path.insert(0, str(CAP))
    try:
        fabric = importlib.import_module("core.protocol_fabric")
        sampler = importlib.import_module("core.shape_sampler")
    finally:
        sys.path[:] = saved_path
        for name in [n for n in sys.modules if n == "core" or n.startswith("core.")]:
            del sys.modules[name]
        sys.modules.update(displaced)
    return fabric, sampler


FABRIC, SAMPLER = _load_sampler_modules()

REGISTRY_PATH = CAP / "profiles" / "current.v1.json"
MATRIX_PATH = CAP / "fixtures" / "shape-sampling-matrix.synthetic.v1.json"
RECEIPT_SCHEMA_PATH = CAP / "schemas" / "shape-sampling-receipt.v1.json"
ENTRYPOINT = CAP / "sample_shapes.py"

PAYLOAD_VALUES = (
    "sample prompt",
    "renamed prompt",
    "C:/work/repo",
    "session-0001",
    "turn-0001",
    "Continue the required work.",
)


def registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


class ShapeSamplerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = SAMPLER.run_sampling_matrix(registry(), matrix())
        cls.by_id = {item["case_id"]: item for item in cls.receipt["cases"]}

    def test_receipt_passes_positive_and_negative_matrix(self) -> None:
        self.assertEqual(self.receipt["state"], "PASS")
        self.assertEqual(self.receipt["failed_case_ids"], [])
        sensitivity = self.receipt["sensitivity"]
        self.assertEqual(sensitivity["state"], "SENSITIVE")
        self.assertEqual(sensitivity["positive_total"], sensitivity["positive_passed"])
        self.assertEqual(sensitivity["negative_total"], sensitivity["negative_passed"])
        self.assertGreaterEqual(sensitivity["negative_total"], 9)
        self.assertGreaterEqual(sensitivity["positive_total"], 7)

    def test_matrix_covers_both_control_and_adversarial_cases(self) -> None:
        kinds = {item["kind"] for item in self.receipt["cases"]}
        self.assertEqual(kinds, {"shape", "config", "lifecycle", "encode"})
        classes = {item["class"] for item in self.receipt["cases"]}
        self.assertEqual(classes, {"POSITIVE", "NEGATIVE"})

    def test_sensitivity_refuses_a_happy_path_only_matrix(self) -> None:
        happy_only = {
            **matrix(),
            "cases": [
                item
                for item in matrix()["cases"]
                if item["class"] == "POSITIVE" and item["kind"] == "shape"
            ],
            "binding_certifications": [],
        }
        receipt = SAMPLER.run_sampling_matrix(registry(), happy_only)
        self.assertEqual(receipt["sensitivity"]["state"], "INSUFFICIENT")
        self.assertEqual(receipt["sensitivity"]["negative_total"], 0)
        self.assertEqual(receipt["sensitivity"]["positive_total"], len(happy_only["cases"]))
        self.assertEqual(receipt["state"], "FAIL")

    def test_receipt_is_deterministic(self) -> None:
        first = SAMPLER.receipt_json(SAMPLER.run_sampling_matrix(registry(), matrix()))
        second = SAMPLER.receipt_json(SAMPLER.run_sampling_matrix(registry(), matrix()))
        self.assertEqual(first, second)
        self.assertNotIn("observed_at", first)

    def test_receipt_never_retains_payload_values(self) -> None:
        serialized = json.dumps(self.receipt)
        for value in PAYLOAD_VALUES:
            self.assertNotIn(value, serialized)
            self.assertNotIn(value.lower(), serialized.lower())
        self.assertFalse(self.receipt["privacy"]["raw_payload_values_persisted"])
        self.assertEqual(
            self.receipt["privacy"]["reused_mechanism"],
            "core.protocol_fabric.shape_fingerprint",
        )

    def test_receipt_only_retains_structural_fingerprints(self) -> None:
        for case in self.receipt["cases"]:
            fingerprint = case["observation_fingerprint"]
            if fingerprint is None:
                continue
            self.assertFalse(fingerprint["content_persisted"])
            self.assertEqual(
                sorted(fingerprint),
                ["content_persisted", "field_count", "field_types", "shape_sha256"],
            )
            for field_type in fingerprint["field_types"]:
                self.assertRegex(field_type, r"^[^:]+:[a-z]+$")

    def test_active_positive_case_is_active_and_canary_only(self) -> None:
        case = self.by_id["positive-active-exact-envelope"]
        self.assertEqual(case["verdict"], "PASS")
        self.assertEqual(case["route_state"], "MATCHED")
        self.assertEqual(case["selected_profile_id"], "cursor-native-common-envelope-v2")
        self.assertEqual(case["lifecycle"]["catalog_state"], "ACTIVE")
        self.assertEqual(case["lifecycle"]["routing_eligibility"], "CANARY_ELIGIBLE")
        self.assertNotEqual(
            case["lifecycle"]["routing_eligibility"], "AUTO_SWITCH_ELIGIBLE"
        )

    def test_legacy_positive_case_falls_back_without_beating_active(self) -> None:
        fallback = self.by_id["positive-legacy-profile-with-explicit-compatibility"]
        self.assertEqual(fallback["selected_profile_id"], "cursor-native-minimal-v1")
        self.assertEqual(fallback["selection_basis"], "COMPATIBILITY_FALLBACK")
        preferred = self.by_id["positive-legacy-is-not-preferred-over-viable-active"]
        self.assertEqual(preferred["selected_profile_id"], "cursor-native-common-envelope-v2")
        self.assertNotEqual(preferred["selected_profile_id"], "cursor-native-minimal-v1")

    def test_prospective_pass_stays_prospective_and_canary_capped(self) -> None:
        case = self.by_id["positive-prospective-synthetic-pass-remains-prospective"]
        self.assertEqual(case["selected_profile_id"], "cursor-native-common-envelope-v2")
        self.assertNotEqual(
            case["selected_profile_id"],
            "cursor-native-common-envelope-v3-prospective",
        )
        lifecycle = FABRIC.validate_lifecycle(
            next(
                profile["lifecycle"]
                for profile in FABRIC.load_profiles(registry())
                if profile["profile_id"] == "cursor-native-common-envelope-v3-prospective"
            )
        )
        self.assertEqual(lifecycle["catalog_state"], "PROSPECTIVE")
        self.assertEqual(lifecycle["validation_state"], "PASS")
        self.assertEqual(lifecycle["max_routing_eligibility"], "CANARY_ELIGIBLE")
        self.assertNotEqual(lifecycle["routing_eligibility"], "AUTO_SWITCH_ELIGIBLE")

    def test_rejected_prospective_replay_is_retained_but_observe_only(self) -> None:
        case = self.by_id["negative-retained-rejected-prospective-replay"]
        self.assertEqual(case["verdict"], "PASS")
        self.assertEqual(case["route_state"], "OBSERVE_ONLY_SHAPE")
        self.assertIsNone(case["selected_profile_id"])
        observed = [
            check
            for check in case["checks"]
            if "observed profiles include" in check["expectation"]
        ]
        self.assertTrue(observed and all(check["satisfied"] for check in observed))
        lifecycle_case = self.by_id["negative-rejected-prospective-cannot-route"]
        self.assertEqual(lifecycle_case["lifecycle"]["validation_state"], "FAIL")
        self.assertEqual(lifecycle_case["lifecycle"]["routing_eligibility"], "OBSERVE_ONLY")
        self.assertEqual(lifecycle_case["lifecycle"]["retained_negative_evidence"], True)

    def test_active_regression_never_silently_uses_a_prospective_candidate(self) -> None:
        case = self.by_id["negative-active-failure-with-no-canary-qualified-replacement"]
        self.assertEqual(case["route_state"], "UNKNOWN_SHAPE")
        self.assertEqual(case["route_reason"], "ACTIVE_SHAPE_REGRESSION")
        self.assertIsNone(case["selected_profile_id"])
        safety = [check for check in case["checks"] if "lifecycle_safety" in check["expectation"]]
        self.assertEqual(len(safety), 3)
        self.assertTrue(all(check["satisfied"] for check in safety))

    def test_unknown_shape_is_observed_and_fingerprinted_without_guessing(self) -> None:
        case = self.by_id["negative-unadmitted-event-alias"]
        self.assertEqual(case["route_state"], "UNKNOWN_SHAPE")
        self.assertEqual(case["route_reason"], "SELF_DESCRIBED_EVENT_MISMATCH")
        self.assertIsNone(case["selected_profile_id"])
        self.assertIsNotNone(case["observation_fingerprint"])
        self.assertFalse(case["observation_fingerprint"]["content_persisted"])

    def test_host_family_isolation_is_enforced(self) -> None:
        case = self.by_id["negative-cross-host-family-shape-mixing"]
        self.assertEqual(case["route_state"], "UNKNOWN_SHAPE")
        self.assertIsNone(case["selected_profile_id"])

    def test_stale_binding_cannot_authorize_current_auto_switching(self) -> None:
        stale_shape = self.by_id["negative-binding-stale-shape-fingerprint"]
        stale_version = self.by_id["negative-binding-stale-host-version"]
        documented = self.by_id["negative-binding-documentation-never-authorizes-routing"]
        for case in (stale_shape, stale_version, documented):
            self.assertEqual(case["verdict"], "PASS")
            self.assertEqual(case["lifecycle"]["routing_eligibility"], "OBSERVE_ONLY")
        self.assertEqual(stale_shape["route_state"], "STALE_SHAPE")
        self.assertEqual(stale_version["route_state"], "STALE_VERSION")
        current = self.by_id["positive-binding-current-live-canary"]
        self.assertEqual(current["route_state"], "CURRENT")
        self.assertEqual(
            current["lifecycle"]["routing_eligibility"], "CANARY_ELIGIBLE"
        )

    def test_sensitivity_fails_when_a_negative_case_starts_passing(self) -> None:
        broken = matrix()
        broken["cases"] = [
            dict(item, expect={"route_state": "MATCHED", "selected_profile_id": "x"})
            if item["case_id"] == "negative-unadmitted-event-alias"
            else item
            for item in broken["cases"]
        ]
        receipt = SAMPLER.run_sampling_matrix(registry(), broken)
        self.assertEqual(receipt["state"], "FAIL")
        self.assertEqual(receipt["sensitivity"]["state"], "FAILED")
        self.assertIn(
            "negative-unadmitted-event-alias",
            receipt["failed_case_ids"],
        )

    def test_receipt_matches_registered_schema_contract(self) -> None:
        schema = json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$id"], "agent-hook-shape-sampling-receipt/v1"
        )
        for key in schema["required"]:
            self.assertIn(key, self.receipt)
        self.assertEqual(self.receipt["schema_version"], schema["$id"])
        self.assertEqual(
            self.receipt["capability_id"],
            "agent-hook-runtime",
        )
        for case in self.receipt["cases"]:
            self.assertIn(case["verdict"], ("PASS", "FAIL"))
            self.assertGreaterEqual(len(case["checks"]), 1)

    def test_capability_registers_sampler_entrypoint_schema_and_matrix(self) -> None:
        capability = json.loads(
            (CAP / "capability.v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            capability["entrypoints"]["shape_sampler"],
            "capabilities/agent-hook-runtime/sample_shapes.py",
        )
        for key in ("shape_sampling_matrix", "shape_sampling_receipt_schema"):
            registered = capability["artifacts"][key]
            self.assertTrue((ROOT / registered).is_file(), registered)
        vocabulary = capability["runtime_boundary"]["lifecycle_vocabulary"]
        self.assertEqual(vocabulary["catalog_states"], list(FABRIC.CATALOG_STATES))
        self.assertEqual(vocabulary["validation_states"], list(FABRIC.VALIDATION_STATES))
        self.assertEqual(vocabulary["proof_classes"], list(FABRIC.PROOF_CLASSES))
        self.assertEqual(
            vocabulary["routing_eligibilities"], list(FABRIC.ROUTING_ELIGIBILITIES)
        )
        self.assertTrue(vocabulary["orthogonal"])

    def test_entrypoint_writes_a_passing_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "receipt.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
                cwd=str(ROOT),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            summary = json.loads(proc.stdout)
            self.assertEqual(summary["state"], "PASS")
            self.assertEqual(summary["schema_version"], "agent-hook-shape-sampling-receipt/v1")
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(written["state"], "PASS")
            self.assertTrue(written["deterministic"])

    def test_registry_declares_orthogonal_lifecycle_vocabulary(self) -> None:
        FABRIC.load_profiles(registry())
        model = registry()["lifecycle_model"]
        self.assertEqual(model["catalog_states"], list(FABRIC.CATALOG_STATES))
        self.assertTrue(model["dimensions_are_orthogonal"])
        self.assertEqual(len(registry()["profiles"]), 6)


if __name__ == "__main__":
    unittest.main()
