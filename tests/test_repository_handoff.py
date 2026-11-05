"""Root admission guard for Automation's portable, canonical handoff capability."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "capabilities/repository-handoff"


class RepositoryHandoffAdmissionTests(unittest.TestCase):
    def test_root_wayfinding_and_owner_separation(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contribution = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        contract = json.loads((CAP / "capability.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["capability_id"], "repository-handoff")
        self.assertEqual(contract["status"], "INCUBATING")
        self.assertIn("repository-handoff", readme)
        self.assertIn("repository-handoff", contribution)
        self.assertIn("TokenCorridor", contract["prompt_ownership"])
        self.assertEqual(contract["production_use_path"], "UNDECLARED")

    def test_incubated_contract_and_synthetic_fixture_agree(self):
        schema = json.loads((CAP / "schemas/handoff.v1.schema.json").read_text(encoding="utf-8"))
        fixture = json.loads((CAP / "fixtures/synthetic-handoff.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], fixture["schema_version"])
        self.assertEqual(set(schema["required"]), set(fixture))
        self.assertIn(fixture["status"], schema["properties"]["status"]["enum"])
        self.assertIn("canonical_path", schema["properties"])
        self.assertNotIn("access_token", fixture)
        self.assertNotIn("worktree_path", fixture)

    def test_capability_never_entitles_provider_mutation(self):
        source = (CAP / "handoff.py").read_text(encoding="utf-8")
        spec = (CAP / "CAPABILITY.md").read_text(encoding="utf-8")
        self.assertIn("WRITTEN_WORKTREE_NOT_COMMITTED", source)
        self.assertIn("exact old-file digest", spec)
        self.assertIn("not remote proof", spec.lower())
        self.assertIn("No silent alternate files", spec)
        for forbidden in ("git push", "force push", "merge", "deploy"):
            self.assertIn(forbidden, " ".join(json.loads(
                (CAP / "capability.v1.json").read_text(encoding="utf-8")
            )["forbidden_operations"]).lower())


if __name__ == "__main__":
    unittest.main()
