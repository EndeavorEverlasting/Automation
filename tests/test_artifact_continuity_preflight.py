from __future__ import annotations
import importlib.util, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"harness/contracts/artifact-continuity-preflight.v1.json"
EXAMPLE=ROOT/"docs/examples/artifact-continuity-preflight.example.json"
VALIDATOR=ROOT/"scripts/validate_artifact_continuity_preflight.py"

def load(p): return json.loads(p.read_text(encoding="utf-8"))
def mod():
    s=importlib.util.spec_from_file_location("preflight_validator",VALIDATOR); assert s and s.loader
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

class ArtifactContinuityPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.contract=load(CONTRACT); cls.v=mod()

    def test_provider_first_example_passes(self):
        self.assertEqual(self.v.validate_packet(load(EXAMPLE),self.contract),[])

    def test_formatting_requires_presentation_fidelity(self):
        p=load(EXAMPLE); p["required_fidelity_dimensions"]=["identity","content","structure"]
        errors=self.v.validate_packet(p,self.contract)
        self.assertTrue(any("presentation fidelity" in e for e in errors))

    def test_known_provider_source_cannot_be_duplicate_canonical(self):
        p=load(EXAMPLE); p["local_output_role"]="CANONICAL_NEW_ARTIFACT"
        self.assertTrue(any("CANONICAL_NEW_ARTIFACT" in e for e in self.v.validate_packet(p,self.contract)))

    def test_unresolved_known_source_blocks_duplicate(self):
        p=load(EXAMPLE); p["exact_source_binding_state"]="UNRESOLVED"; p["sync_obligation"]="PENDING_SOURCE_RESOLUTION"; p["result_state"]="BLOCKED_SOURCE_RESOLUTION"
        self.assertEqual(self.v.validate_packet(p,self.contract),[])

    def test_provider_unavailable_requires_sync_obligation(self):
        p=load(EXAMPLE); p["provider_access_state"]="UNAVAILABLE"; p["provider_write_state"]="UNAVAILABLE"; p["sync_obligation"]="PENDING_PROVIDER_SYNC"; p["result_state"]="READY_LOCAL_WITH_SYNC_OBLIGATION"
        self.assertEqual(self.v.validate_packet(p,self.contract),[])
        p["sync_obligation"]="NONE_PENDING"
        self.assertTrue(any("PENDING_PROVIDER_SYNC" in e for e in self.v.validate_packet(p,self.contract)))

    def test_provider_edit_without_write_authority_blocks(self):
        p=load(EXAMPLE); p["provider_write_state"]="READ_ONLY"; p["result_state"]="BLOCKED_PROVIDER_WRITE"
        self.assertEqual(self.v.validate_packet(p,self.contract),[])

    def test_no_provider_source_is_explicit(self):
        p=load(EXAMPLE); p.update({"known_provider_source":False,"exact_source_binding_state":"NOT_APPLICABLE","provider_access_state":"NOT_APPLICABLE","provider_write_state":"NOT_APPLICABLE","local_output_role":"CANONICAL_LOCAL","provider_link_policy":"NOT_APPLICABLE","sync_obligation":"NONE_PENDING","result_state":"READY_NO_PROVIDER_SOURCE"})
        self.assertEqual(self.v.validate_packet(p,self.contract),[])

    def test_raw_provider_locator_rejected(self):
        p=load(EXAMPLE)
        p["artifact_semantic_id"]="https://"+"docs.google"+".com/document/d/private"
        self.assertTrue(any("raw provider locator" in e for e in self.v.validate_packet(p,self.contract)))


    def test_provider_neutral_url_is_rejected(self):
        p=load(EXAMPLE)
        p["artifact_semantic_id"]="scheme"+"://opaque"
        self.assertTrue(any("raw provider locator" in e for e in self.v.validate_packet(p,self.contract)))

    def test_known_resolved_source_rejects_not_applicable_access(self):
        p=load(EXAMPLE)
        p["provider_access_state"]="NOT_APPLICABLE"
        errors=self.v.validate_packet(p,self.contract)
        self.assertTrue(any("concrete provider_access_state" in e for e in errors))

    def test_known_available_read_cannot_claim_no_provider_source(self):
        p=load(EXAMPLE)
        p["artifact_action"]="read"
        p["required_fidelity_dimensions"]=["identity","content"]
        p["result_state"]="READY_NO_PROVIDER_SOURCE"
        errors=self.v.validate_packet(p,self.contract)
        self.assertTrue(any("READY_PROVIDER_FIRST" in e for e in errors))

    def test_no_provider_source_requires_not_applicable_provider_state(self):
        p=load(EXAMPLE)
        p.update({
            "known_provider_source":False,
            "exact_source_binding_state":"NOT_APPLICABLE",
            "provider_link_policy":"NOT_APPLICABLE",
            "result_state":"READY_NO_PROVIDER_SOURCE",
            "provider_access_state":"AVAILABLE",
            "provider_write_state":"AUTHORIZED",
            "sync_obligation":"PENDING_PROVIDER_SYNC",
        })
        errors=self.v.validate_packet(p,self.contract)
        joined=" | ".join(errors)
        self.assertIn("NOT_APPLICABLE",joined)
        self.assertIn("NONE_PENDING",joined)

    def test_future_inheritance_is_contractual(self):
        self.assertIn("root wayfinding",self.contract["future_inheritance"]["new_repository_rule"])
        self.assertIn("recopying"," ".join(self.contract["invariants"]).lower())
        self.assertIn("fidelity",self.contract["future_inheritance"]["capability_relationship"])

if __name__=="__main__": unittest.main()
