from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "harness/contracts/seam-boundary-review.v1.json"
DOC_PATH = ROOT / "docs/SEAM_BOUNDARY_REVIEW.md"


class SeamBoundaryReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_contract_carries_prompt_scratch_doctrine(self) -> None:
        self.assertEqual(
            self.contract["schema_version"],
            "automation-seam-boundary-review/v1",
        )
        self.assertEqual(
            self.contract["source_ideas"],
            [f"PS-{n:04d}" for n in range(50, 57)],
        )

    def test_review_covers_owner_consumer_discoverability_and_cleanup(self) -> None:
        questions = {item["id"]: item for item in self.contract["review_questions"]}
        self.assertEqual(set(questions), {f"SB{n:02d}" for n in range(1, 11)})
        for phrase in (
            "True owner",
            "Consumer knowledge",
            "Discoverability",
            "Isolated consumer canary",
            "Obsolete workaround removal",
        ):
            self.assertIn(phrase, {item["name"] for item in questions.values()})

    def test_anti_pattern_library_is_concrete_and_repairable(self) -> None:
        patterns = self.contract["anti_patterns"]
        self.assertGreaterEqual(len(patterns), 10)
        for item in patterns:
            self.assertTrue(item["smell"])
            self.assertTrue(item["example"])
            self.assertTrue(item["repair"])
        names = {item["name"] for item in patterns}
        self.assertIn("Upstream by ownership, internal by interface", names)
        self.assertIn("Adapter multiplication", names)
        self.assertIn("Invisible contract", names)
        self.assertIn("Interface-only repair", names)
        self.assertIn("False portability", names)

    def test_repair_sequence_requires_real_consumer_and_workaround_deletion(self) -> None:
        sequence = " | ".join(self.contract["repair_sequence"]).lower()
        self.assertIn("migrate one representative real consumer", sequence)
        self.assertIn("isolated-consumer", sequence)
        self.assertIn("delete compensating downstream machinery", sequence)
        self.assertIn("regressions preventing obsolete paths", sequence)

    def test_root_wayfinding_exposes_the_contract(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for body in (agents, contributing, readme):
            self.assertIn("seam-boundary-review.v1.json", body)
        self.assertIn("Consumer Knowledge Test", agents)
        self.assertIn("Isolated Consumer Canary", agents)

    def test_human_doc_generalizes_beyond_prompt_resolver_case(self) -> None:
        doc = DOC_PATH.read_text(encoding="utf-8")
        for marker in (
            "## Cross-domain anti-pattern examples",
            "| Scheduler |",
            "| Data layer |",
            "| Package/library |",
            "| Generated artifacts |",
            "| Provider bridge |",
            "| Agent harness |",
        ):
            self.assertIn(marker, doc)


if __name__ == "__main__":
    unittest.main()
