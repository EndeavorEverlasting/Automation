from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "harness/contracts/runtime-execution-handoff.v1.json"
EXAMPLE_PATH = ROOT / "docs/examples/runtime-handoff.example.json"
VALIDATOR_PATH = ROOT / "scripts/validate_runtime_handoff.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("runtime_handoff_validator", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeHandoffContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        cls.validator = load_validator_module()

    def test_contract_consumes_runtime_partition_without_becoming_planner(self) -> None:
        self.assertEqual(
            self.contract["schema_version"],
            "automation-runtime-execution-handoff/v1",
        )
        self.assertEqual(
            self.contract["semantic_dependency"],
            "planning.runtime_partition",
        )
        self.assertEqual(
            self.contract["role"],
            "consumer_validation_only",
        )
        self.assertIn(
            "LOCAL_AGENT_RUNTIME",
            self.contract["execution_environments"],
        )
        self.assertIn(
            "UNKNOWN_RUNTIME",
            self.contract["execution_environments"],
        )

    def test_sanitized_ready_example_passes(self) -> None:
        errors = self.validator.validate_packet(
            self.example,
            self.contract,
            require_ready=True,
        )
        self.assertEqual(errors, [])

    def test_ready_packet_fails_closed_on_unknown_runtime(self) -> None:
        packet = copy.deepcopy(self.example)
        packet["execution_environment"] = "UNKNOWN_RUNTIME"
        errors = self.validator.validate_packet(
            packet,
            self.contract,
            require_ready=True,
        )
        self.assertTrue(any("UNKNOWN_RUNTIME" in error for error in errors))

    def test_private_drive_locator_is_rejected(self) -> None:
        packet = copy.deepcopy(self.example)
        packet["evidence_inputs"].append(
            {
                "type": "private_locator",
                "value": "https://drive.google.com/drive/folders/PRIVATE",
            }
        )
        errors = self.validator.validate_packet(packet, self.contract)
        self.assertTrue(any("privacy violation" in error for error in errors))

    def test_person_specific_home_path_is_rejected(self) -> None:
        packet = copy.deepcopy(self.example)
        packet["owned_scope"].append("/home/example-user/private-checkout")
        errors = self.validator.validate_packet(packet, self.contract)
        self.assertTrue(any("forbidden path pattern" in error for error in errors))

    def test_required_scope_and_proof_fields_fail_closed(self) -> None:
        packet = copy.deepcopy(self.example)
        packet.pop("forbidden_scope")
        packet["acceptance_gates"] = []
        packet["proof_ceiling"] = ""
        errors = self.validator.validate_packet(packet, self.contract)
        self.assertTrue(any("missing required field: forbidden_scope" in error for error in errors))
        self.assertTrue(any("acceptance_gates must be a non-empty list" in error for error in errors))
        self.assertTrue(any("proof_ceiling must be a non-empty string" in error for error in errors))

    def test_common_secret_and_private_state_keys_are_rejected(self) -> None:
        for forbidden_key in (
            "api_key",
            "client_secret",
            "credential_blob",
            "session_state",
            "browser_state",
        ):
            with self.subTest(forbidden_key=forbidden_key):
                packet = copy.deepcopy(self.example)
                packet["evidence_inputs"].append(
                    {
                        "type": "private_state",
                        forbidden_key: "synthetic-sensitive-value",
                    }
                )
                errors = self.validator.validate_packet(packet, self.contract)
                self.assertTrue(any("privacy violation" in error for error in errors))

    def test_non_object_json_root_fails_closed(self) -> None:
        for packet in ([], "not-an-object", 42):
            with self.subTest(packet=packet):
                errors = self.validator.validate_packet(
                    packet,
                    self.contract,
                    require_ready=True,
                )
                self.assertEqual(errors, ["packet root must be a JSON object"])

    def test_list_items_must_contain_meaningful_data(self) -> None:
        cases = (
            ("owned_scope", [""]),
            ("required_capabilities", [None]),
            ("evidence_inputs", [{}]),
        )
        for field, value in cases:
            with self.subTest(field=field):
                packet = copy.deepcopy(self.example)
                packet[field] = value
                errors = self.validator.validate_packet(packet, self.contract)
                self.assertTrue(
                    any(
                        f"{field}[0] must contain meaningful non-null data" in error
                        for error in errors
                    )
                )

    def test_root_wayfinding_exposes_runtime_and_privacy_contracts(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for body in (readme, agents, contributing):
            self.assertIn("runtime-execution-handoff.v1.json", body)
        self.assertIn("PUBLIC_PRIVATE_BRIDGE.md", readme)
        self.assertIn("No contract may assume a frontier model", agents)


if __name__ == "__main__":
    unittest.main()
