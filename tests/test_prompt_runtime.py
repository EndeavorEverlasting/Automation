from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prompt_runtime.py"
SPEC = importlib.util.spec_from_file_location("prompt_runtime", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class FakeFetch:
    def __init__(self):
        self.files = {}

    def put(self, repo, path, ref, payload, sha=None):
        self.files[(repo, path, ref)] = (
            payload,
            {
                "repository": repo,
                "path": path,
                "ref": ref,
                "blob_sha": sha or ("sha-" + path.replace("/", "-")),
                "html_url": f"https://example.invalid/{repo}/{path}",
            },
        )

    def __call__(self, repo, path, ref):
        try:
            return self.files[(repo, path, ref)]
        except KeyError as exc:
            raise MOD.PromptSourceError(f"missing fixture: {repo}@{ref}:{path}") from exc


class PromptRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schema_version": "automation-prompt-sources/v1",
            "portable": {
                "repository": "Owner/Portable",
                "repository_env": "TEST_PORTABLE_REPO",
                "ref": "main",
                "ref_env": "TEST_PORTABLE_REF",
                "product_boundaries_path": "pk/registry/prompts/product-boundaries.v1.json",
                "promptkit_root": "pk",
            },
            "retained": {
                "repository": "Owner/Retained",
                "repository_env": "TEST_RETAINED_REPO",
                "ref": "main",
                "ref_env": "TEST_RETAINED_REF",
            },
        }
        self.fetch = FakeFetch()
        boundaries = {
            "shared_inputs": {
                "base_registry": "registry/base/prompts.json",
                "content_registries": ["registry/prompts/spec.v1.json"],
            },
            "products": {
                "afk-agent-flow": {"extension_registries": []},
                "triage-local-operations": {
                    "donor_retained_registries": [
                        "registry/prompts/retained.v1.json"
                    ]
                },
            },
        }
        self.fetch.put(
            "Owner/Portable",
            "pk/registry/prompts/product-boundaries.v1.json",
            "main",
            boundaries,
        )
        self.fetch.put(
            "Owner/Portable",
            "pk/registry/base/prompts.json",
            "main",
            [{"id": "P04", "name": "Planner", "copyContent": "P04 BODY"}],
        )
        self.fetch.put(
            "Owner/Portable",
            "pk/registry/prompts/spec.v1.json",
            "main",
            {
                "prompts": [
                    {
                        "id": "P92",
                        "name": "Canonical Path Prompt",
                        "type": "VERIFY + REPAIR",
                        "class": "HARNESS / CANONICAL PATH",
                        "copyContent": "P92 BODY",
                    }
                ]
            },
            sha="p92-blob",
        )
        self.fetch.put(
            "Owner/Retained",
            "registry/prompts/retained.v1.json",
            "main",
            [{"id": "P125", "name": "Retained", "copyContent": "P125 BODY"}],
        )

    def resolve(self, text):
        return MOD.resolve_prompt_invocation(text, self.config, self.fetch)

    def test_invoke_and_implement_p92_resolves_exact_body(self):
        result = self.resolve("invoke & implement P92")
        self.assertEqual(result["intent"], "EXECUTE_AND_IMPLEMENT")
        self.assertTrue(result["execution_required"])
        self.assertTrue(result["implementation_required"])
        self.assertEqual(result["overall_state"], "RESOLVED")
        resolved = result["resolutions"][0]
        self.assertEqual(resolved["state"], "RESOLVED_PORTABLE")
        self.assertEqual(resolved["source_blob_sha"], "p92-blob")
        self.assertEqual(resolved["copy_content"], "P92 BODY")
        self.assertEqual(
            resolved["copy_content_sha256"],
            hashlib.sha256(b"P92 BODY").hexdigest(),
        )

    def test_bare_prompt_is_execution(self):
        result = self.resolve("P92")
        self.assertEqual(result["intent"], "EXECUTE")
        self.assertTrue(result["execution_required"])

    def test_reference_does_not_execute(self):
        result = self.resolve("what is P92?")
        self.assertEqual(result["intent"], "REFERENCE")
        self.assertFalse(result["execution_required"])

    def test_unknown_prompt_fails_closed_without_fuzzy_match(self):
        result = self.resolve("invoke P99")
        self.assertEqual(result["overall_state"], "UNRESOLVED")
        self.assertEqual(result["resolutions"][0]["state"], "UNRESOLVED")

    def test_retained_prompt_resolves_from_retained_owner(self):
        result = self.resolve("run P125")
        resolved = result["resolutions"][0]
        self.assertEqual(resolved["state"], "RESOLVED_RETAINED")
        self.assertEqual(resolved["canonical_repository"], "Owner/Retained")

    def test_cross_owner_duplicate_is_conflict(self):
        self.fetch.put(
            "Owner/Retained",
            "registry/prompts/retained.v1.json",
            "main",
            [{"id": "P92", "name": "Bad duplicate", "copyContent": "BAD"}],
        )
        result = self.resolve("invoke P92")
        self.assertEqual(result["overall_state"], "SOURCE_CONFLICT")

    def test_source_failure_is_provider_lookup_required(self):
        del self.fetch.files[
            ("Owner/Portable", "pk/registry/prompts/spec.v1.json", "main")
        ]
        result = self.resolve("invoke P92")
        self.assertEqual(result["overall_state"], "PROVIDER_LOOKUP_REQUIRED")

    def test_repository_and_ref_can_move_without_code_change(self):
        with patch.dict(
            os.environ,
            {
                "TEST_PORTABLE_REPO": "Renamed/ControlPlane",
                "TEST_PORTABLE_REF": "stable",
            },
            clear=False,
        ):
            repo, ref = MOD._resolved_source(self.config["portable"])
        self.assertEqual(repo, "Renamed/ControlPlane")
        self.assertEqual(ref, "stable")


if __name__ == "__main__":
    unittest.main()
