from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_PATH = ROOT / "capabilities" / "document-formatting" / "core" / "compiler.py"
ADAPTER_PATH = ROOT / "capabilities" / "document-formatting" / "adapters" / "google_docs.py"
DESIGN = ROOT / "capabilities" / "document-formatting" / "fixtures" / "design-spec.synthetic.v1.json"
SOURCE = ROOT / "capabilities" / "document-formatting" / "fixtures" / "document-source.synthetic.v1.json"

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

COMPILER = load_module("document_formatting_compiler_test", COMPILER_PATH)
ADAPTER = load_module("document_formatting_google_docs_test", ADAPTER_PATH)


class DocumentFormattingCompilerP95Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design = json.loads(DESIGN.read_text(encoding="utf-8"))
        cls.source = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_success_stack_is_deterministic_and_provider_neutral(self):
        first, first_receipt = COMPILER.compile_document(self.source, self.design)
        second, second_receipt = COMPILER.compile_document(copy.deepcopy(self.source), copy.deepcopy(self.design))
        self.assertEqual(COMPILER.canonical_json_bytes(first), COMPILER.canonical_json_bytes(second))
        self.assertEqual(first_receipt, second_receipt)
        self.assertEqual("COMPILED_PROVIDER_NEUTRAL_DOCUMENT", first_receipt["state"])
        self.assertEqual(2, first["metrics"]["internal_link_count"])
        self.assertEqual(1, first["metrics"]["named_external_link_count"])
        self.assertEqual(1, first["metrics"]["image_count"])
        serialized = json.dumps(first).lower()
        self.assertNotIn("google docs", serialized)
        self.assertNotIn("nyc health", serialized)

    def test_failure_stack_rejects_raw_visible_url(self):
        source = copy.deepcopy(self.source)
        source["sections"][0]["blocks"][0]["text"] = "Open https://example.test/raw directly."
        with self.assertRaises(COMPILER.DocumentCompileError) as ctx:
            COMPILER.compile_document(source, self.design)
        self.assertEqual("DF_RAW_VISIBLE_URL", ctx.exception.code)

    def test_failure_stack_requires_declared_component_in_semantic_section(self):
        source = copy.deepcopy(self.source)
        source["sections"][1]["blocks"] = [{"type": "paragraph", "text": "Evidence omitted."}]
        with self.assertRaises(COMPILER.DocumentCompileError) as ctx:
            COMPILER.compile_document(source, self.design)
        self.assertEqual("DF_REQUIRED_COMPONENT", ctx.exception.code)

    def test_palette_and_non_color_fingerprints_are_independent(self):
        baseline, _ = COMPILER.compile_document(self.source, self.design)
        palette = copy.deepcopy(self.design)
        palette["palette"]["accent"] = "#123456"
        palette_ir, _ = COMPILER.compile_document(self.source, palette)
        self.assertEqual(baseline["fingerprints"]["non_color_aesthetic"], palette_ir["fingerprints"]["non_color_aesthetic"])
        self.assertNotEqual(baseline["fingerprints"]["palette"], palette_ir["fingerprints"]["palette"])

        mechanics = copy.deepcopy(self.design)
        mechanics["roles"]["H1"]["mechanics"]["size_pt"] = 17
        mechanics_ir, _ = COMPILER.compile_document(self.source, mechanics)
        self.assertNotEqual(baseline["fingerprints"]["non_color_aesthetic"], mechanics_ir["fingerprints"]["non_color_aesthetic"])

    def test_google_docs_adapter_success_stack_is_two_phase_for_internal_links(self):
        ir, _ = COMPILER.compile_document(self.source, self.design)
        plan = ADAPTER.build_plan(
            ir,
            required_features=[
                "semantic_headings",
                "internal_navigation",
                "named_external_links",
                "inline_images",
                "revision_readback",
            ],
        )
        self.assertEqual("ADAPTER_PLAN_READY", plan["state"])
        self.assertEqual(
            ["CONSTRUCT_AND_STYLE", "RESOLVE_HEADING_IDENTITIES", "APPLY_INTERNAL_LINKS", "FINAL_READBACK"],
            [phase["phase_id"] for phase in plan["phases"]],
        )
        self.assertTrue(plan["phases"][0]["requires_revision_control"])
        self.assertTrue(plan["phases"][2]["requires_revision_control"])

    def test_google_docs_adapter_fails_closed_on_dynamic_page_fields(self):
        ir, _ = COMPILER.compile_document(self.source, self.design)
        with self.assertRaises(ADAPTER.GoogleDocsAdapterError) as ctx:
            ADAPTER.build_plan(ir, required_features=["dynamic_page_fields"])
        self.assertEqual("GDA_UNSUPPORTED_FEATURE", ctx.exception.code)
        self.assertIn("READABLE_EXISTING_NOT_CREATABLE", str(ctx.exception))

    def test_core_has_no_hh_consumer_assumptions(self):
        source = COMPILER_PATH.read_text(encoding="utf-8").lower()
        adapter = ADAPTER_PATH.read_text(encoding="utf-8").lower()
        forbidden = ("nyc health", "northwell", "hh-metropolitan", "cc reader")
        self.assertFalse(any(item in source for item in forbidden))
        self.assertFalse(any(item in adapter for item in forbidden))


if __name__ == "__main__":
    unittest.main()
