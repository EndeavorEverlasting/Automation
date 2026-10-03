from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prompt_runtime.py"
SPEC = importlib.util.spec_from_file_location("prompt_runtime", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class PromptRuntimeTests(unittest.TestCase):
    def test_invoke_and_implement_p92_uses_upstream_contract(self):
        result = MOD.resolve("invoke & implement P92")
        self.assertEqual(result["overall_state"], "RESOLVED")
        self.assertEqual(result["intent"], "EXECUTE_AND_IMPLEMENT")
        self.assertTrue(result["execution_required"])
        self.assertTrue(result["implementation_required"])
        self.assertEqual(result["upstream_contract"], "prompt-invocation-upstream/v1")
        self.assertEqual(result["resolution_mode"], "UPSTREAM_CATALOG_PINNED")
        resolved = result["resolutions"][0]
        self.assertEqual(resolved["state"], "RESOLVED_UPSTREAM")
        self.assertEqual(resolved["prompt_id"], "P92")
        self.assertEqual(resolved["name"], "Canonical Path Prompt")

    def test_retained_prompt_resolves_without_triage_knowledge(self):
        result = MOD.resolve("invoke P125")
        self.assertEqual(result["overall_state"], "RESOLVED")
        resolved = result["resolutions"][0]
        self.assertEqual(resolved["state"], "RESOLVED_UPSTREAM")
        self.assertEqual(resolved["authority_kind"], "RETAINED_REPOSITORY_LOCAL")
        self.assertTrue(resolved["copy_content"])

    def test_reference_does_not_execute(self):
        result = MOD.resolve("what is P92?")
        self.assertEqual(result["intent"], "REFERENCE")
        self.assertFalse(result["execution_required"])

    def test_unknown_prompt_fails_closed(self):
        result = MOD.resolve("invoke P999")
        self.assertEqual(result["overall_state"], "UNRESOLVED")

    def test_vendor_manifest_pins_one_upstream_contract(self):
        manifest = json.loads(MOD.UPSTREAM_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["dependency_id"], "prompt-invocation-upstream")
        self.assertEqual(manifest["contract_id"], "prompt-invocation-upstream/v1")
        self.assertEqual(
            manifest["upstream_commit"],
            "0755b08eca0c4e105d3724b47dd2e43a25f67bee",
        )
        files = {item["local_path"] for item in manifest["files"]}
        self.assertEqual(
            files,
            {
                "vendor/prompt-invocation-upstream/contract.v1.json",
                "vendor/prompt-invocation-upstream/catalog.v1.json",
                "vendor/prompt-invocation-upstream/prompt_invocation_resolver.py",
            },
        )

    def test_downstream_does_not_encode_promptkit_topology(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "product-boundaries",
            "management-operations-prompts",
            "web-excel-repair-triage",
            "GitHubContentsClient",
            "promptkit_root",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
