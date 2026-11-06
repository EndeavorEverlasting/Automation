from __future__ import annotations
import importlib.util, json, re, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAP=ROOT/"capabilities/artifact-sync"
BINDING=CAP/"schemas/binding.v1.json"
RECEIPT=CAP/"schemas/receipt.v1.json"
BINDING_EXAMPLE=CAP/"fixtures/binding.example.v1.json"
INVALID_FORMAT_RECEIPT=CAP/"fixtures/receipt.formatting-local-only-invalid.v1.json"
VALID_FORMAT_RECEIPT=CAP/"fixtures/receipt.formatting-provider-verified.v1.json"
HANDOFF=ROOT/"docs/examples/runtime-handoff.artifact-sync-rust-cli.json"
PLAN=ROOT/"docs/plans/P04_ARTIFACT_SYNC_FACTORING_2026-10-03.md"
BINDING_VALIDATOR=ROOT/"scripts/validate_artifact_sync_binding.py"
RECEIPT_VALIDATOR=ROOT/"scripts/validate_artifact_sync_receipt.py"
RUNTIME_VALIDATOR=ROOT/"scripts/validate_runtime_handoff.py"
RUNTIME_CONTRACT=ROOT/"harness/contracts/runtime-execution-handoff.v1.json"

def load(path): return json.loads(path.read_text(encoding="utf-8"))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); assert spec and spec.loader
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

class ArtifactSyncContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding_contract=load(BINDING)
        cls.binding_validator=module("artifact_sync_binding_validator",BINDING_VALIDATOR)
        cls.receipt_contract=load(RECEIPT)
        cls.receipt_validator=module("artifact_sync_receipt_validator",RECEIPT_VALIDATOR)

    def test_capability_declares_preflight_and_baseline(self):
        cap=load(CAP/"capability.v1.json")
        self.assertEqual(cap["capability_id"],"artifact-sync")
        self.assertEqual(cap["status"],"CONTRACT_DEFINED_RUST_IMPLEMENTATION_PENDING")
        self.assertEqual(cap["schemas"]["preflight"],"harness/contracts/artifact-continuity-preflight.v1.json")
        self.assertIn("durable common-baseline recovery contract",cap["core_owns"])

    def test_binding_fixture_fully_validates(self):
        binding=load(BINDING_EXAMPLE)
        self.assertEqual(self.binding_validator.validate_binding(binding,self.binding_contract),[])
        self.assertEqual(binding["local_materialization"]["mode"],"ephemeral")
        self.assertEqual(binding["baseline_state"]["state_resolution"],"private_runtime_only")
        self.assertEqual(binding["sync_policy"]["conflict_policy"],"fail_closed")

    def test_local_and_bidirectional_require_explicit_local_side(self):
        for authority in ("local","bidirectional"):
            b=load(BINDING_EXAMPLE); b["authority"]=authority
            errors=self.binding_validator.validate_binding(b,self.binding_contract)
            self.assertTrue(any("local_side" in e for e in errors))

    def test_missing_baseline_fails(self):
        b=load(BINDING_EXAMPLE); b.pop("baseline_state")
        self.assertTrue(any("baseline_state" in e for e in self.binding_validator.validate_binding(b,self.binding_contract)))

    def test_contract_distinguishes_pull_from_provider_bound_write(self):
        rules=" ".join(self.receipt_contract["sanitized_tracking_rules"]).lower()
        self.assertIn("pull may report synced without a provider write",rules)
        self.assertIn("push/reconcile",rules)
        self.assertIn("BLOCKED_NO_BASELINE",self.receipt_contract["states"])

    def test_local_only_formatting_claim_is_rejected(self):
        errors=self.receipt_validator.validate_receipt(load(INVALID_FORMAT_RECEIPT),self.receipt_contract)
        joined=" | ".join(errors).lower()
        self.assertIn("presentation",joined)
        self.assertIn("provider_write_performed",joined)
        self.assertIn("read_back_verified",joined)

    def test_provider_verified_formatting_control_passes(self):
        self.assertEqual(self.receipt_validator.validate_receipt(load(VALID_FORMAT_RECEIPT),self.receipt_contract),[])

    def test_public_scope_has_no_raw_provider_locators(self):
        patterns=(re.compile(r"https://(?:drive|docs)\.google\.com/",re.I),re.compile(r"\bdrive_file_id\b",re.I),re.compile(r"\bgoogle_drive_id\b",re.I))
        paths=[p for p in CAP.rglob("*") if p.is_file()]+[PLAN,ROOT/"docs/ARTIFACT_CONTINUITY_PREFLIGHT.md"]
        for path in paths:
            text=path.read_text(encoding="utf-8")
            for pat in patterns: self.assertIsNone(pat.search(text),f"{path}: {pat.pattern}")

    def test_cursor_handoff_is_ready_and_inherits_preflight(self):
        m=module("runtime_handoff_validator",RUNTIME_VALIDATOR)
        packet=load(HANDOFF); contract=load(RUNTIME_CONTRACT)
        self.assertEqual(m.validate_packet(packet,contract,require_ready=True),[])
        self.assertEqual(packet["execution_environment"],"LOCAL_AGENT_RUNTIME")
        identities={x["identity"] for x in packet["evidence_inputs"]}
        self.assertIn("artifact-continuity-preflight/v1",identities)
        self.assertTrue(any("durable-baseline" in x for x in packet["forbidden_scope"]))

    def test_root_wayfinding_exposes_sync_and_preflight(self):
        for path in (ROOT/"README.md",ROOT/"AGENTS.md",ROOT/"CONTRIBUTING.md"):
            text=path.read_text(encoding="utf-8").lower()
            self.assertIn("artifact-sync",text)
            self.assertIn("artifact-continuity-preflight",text)

if __name__=="__main__": unittest.main()
