from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP_ROOT = ROOT / "capabilities/artifact-sync"
BINDING_CONTRACT = CAP_ROOT / "schemas/binding.v1.json"
RECEIPT_CONTRACT = CAP_ROOT / "schemas/receipt.v1.json"
BINDING_EXAMPLE = CAP_ROOT / "fixtures/binding.example.v1.json"
HANDOFF = ROOT / "docs/examples/runtime-handoff.artifact-sync-rust-cli.json"
RUNTIME_VALIDATOR = ROOT / "scripts/validate_runtime_handoff.py"
RUNTIME_CONTRACT = ROOT / "harness/contracts/runtime-execution-handoff.v1.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ArtifactSyncContractTests(unittest.TestCase):
    def test_capability_declares_frozen_v1_semantics(self) -> None:
        cap = _load(CAP_ROOT / "capability.v1.json")
        self.assertEqual(cap["capability_id"], "artifact-sync")
        self.assertEqual(cap["status"], "CONTRACT_DEFINED_RUST_IMPLEMENTATION_PENDING")
        self.assertEqual(cap["conflict_policy_floor"], "fail_closed")
        self.assertEqual(cap["implementation_language"], "Rust")
        self.assertIn("ephemeral", cap["local_materialization_modes"])
        self.assertIn(
            "raw-byte replacement of provider-native document formats",
            cap["forbidden_core_assumptions"],
        )

    def test_binding_fixture_is_provider_authoritative_and_storage_bounded(self) -> None:
        binding = _load(BINDING_EXAMPLE)
        self.assertEqual(binding["schema_version"], "artifact-sync-binding/v1")
        self.assertEqual(binding["authority"], "provider")
        self.assertEqual(binding["local_materialization"]["mode"], "ephemeral")
        self.assertFalse(binding["local_materialization"]["retain_after_success"])
        self.assertEqual(binding["local_materialization"]["max_retained_bytes"], 0)
        self.assertEqual(binding["sync_policy"]["conflict_policy"], "fail_closed")
        self.assertEqual(
            binding["sync_policy"]["native_write_policy"],
            "provider_native_api_required",
        )
        self.assertEqual(
            binding["provider"]["locator_resolution"],
            "private_runtime_only",
        )

    def test_contracts_define_checkpoint_and_readback_gates(self) -> None:
        binding = _load(BINDING_CONTRACT)
        receipt = _load(RECEIPT_CONTRACT)
        self.assertEqual(binding["schema_version"], "artifact-sync-binding/v1")
        self.assertEqual(receipt["schema_version"], "artifact-sync-receipt/v1")
        self.assertEqual(
            set(binding["checkpoint_triggers"]),
            {"before_consume", "after_mutation", "handoff", "periodic"},
        )
        joined = " ".join(binding["sync_rules"]).lower()
        self.assertIn("read-back verification", joined)
        self.assertIn("blocked_conflict", " ".join(receipt["states"]).lower())

    def test_public_artifact_sync_files_do_not_embed_raw_provider_locators(self) -> None:
        forbidden = (
            re.compile(r"https://(?:drive|docs)\.google\.com/", re.I),
            re.compile(r"\bdrive_file_id\b", re.I),
            re.compile(r"\bgoogle_drive\b", re.I),
        )
        for path in CAP_ROOT.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                self.assertIsNone(pattern.search(text), f"{path}: {pattern.pattern}")

    def test_cursor_handoff_is_ready_and_privacy_safe(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "runtime_handoff_validator", RUNTIME_VALIDATOR
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        packet = _load(HANDOFF)
        contract = _load(RUNTIME_CONTRACT)
        self.assertEqual(
            module.validate_packet(packet, contract, require_ready=True),
            [],
        )
        self.assertEqual(packet["execution_environment"], "LOCAL_AGENT_RUNTIME")
        self.assertIn(
            "artifact-sync v1 authority, privacy, storage, or conflict-policy redesign",
            packet["forbidden_scope"],
        )

    def test_root_wayfinding_exposes_artifact_sync(self) -> None:
        for path in (ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md"):
            self.assertIn("artifact-sync", path.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
