from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_PATH = ROOT / "capabilities" / "document-formatting" / "core" / "compiler.py"
ADAPTER_PATH = ROOT / "capabilities" / "document-formatting" / "adapters" / "google_docs.py"
DESIGN = ROOT / "capabilities" / "document-formatting" / "fixtures" / "design-spec.synthetic.v1.json"
SOURCE = ROOT / "capabilities" / "document-formatting" / "fixtures" / "document-source.synthetic.v1.json"
COMPILE_CLI = ROOT / "capabilities" / "document-formatting" / "compile.py"
ADAPTER_CLI = ROOT / "capabilities" / "document-formatting" / "adapters" / "google_docs.py"
SOURCE_SCHEMA = ROOT / "capabilities" / "document-formatting" / "schemas" / "source.v1.json"
IR_SCHEMA = ROOT / "capabilities" / "document-formatting" / "schemas" / "ir.v1.json"
DEGRADATION_POLICY = ROOT / "capabilities" / "document-formatting" / "fixtures" / "google-docs-degradation-policy.synthetic.v1.json"

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



    def test_design_spec_rejects_multi_role_block_mapping(self):
        design = copy.deepcopy(self.design)
        design["block_component_map"]["paragraph"] = ["BODY", "WARNING"]
        errors = COMPILER.validate_design_spec(design)
        self.assertTrue(
            any("must reference exactly one role" in error for error in errors),
            errors,
        )
        with self.assertRaises(COMPILER.DocumentCompileError) as ctx:
            COMPILER.compile_document(self.source, design)
        self.assertEqual("DF_DESIGN_SPEC", ctx.exception.code)

    def test_google_docs_internal_links_preserve_ordered_placeholders(self):
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
        construct = plan["phases"][0]["operations"]
        placeholders = [
            operation
            for operation in construct
            if operation["operation"] == "insert_internal_link_placeholder"
        ]
        bindings = plan["phases"][2]["operations"]
        self.assertEqual(2, len(placeholders))
        self.assertEqual(
            [item["placeholder_id"] for item in placeholders],
            [item["placeholder_id"] for item in bindings],
        )
        source_orders = [item["source_order"] for item in construct]
        self.assertEqual(sorted(source_orders), source_orders)

    def test_adapter_rejects_malformed_ir_with_typed_error(self):
        ir, _ = COMPILER.compile_document(self.source, self.design)
        malformed = copy.deepcopy(ir)
        del malformed["blocks"][0]["style"]
        with self.assertRaises(ADAPTER.GoogleDocsAdapterError) as ctx:
            ADAPTER.build_plan(malformed, required_features=["semantic_headings"])
        self.assertEqual("GDA_IR_SCHEMA", ctx.exception.code)
        self.assertIn("style must be an object", str(ctx.exception))

    def test_published_schemas_encode_runtime_required_shapes(self):
        source_schema = json.loads(SOURCE_SCHEMA.read_text(encoding="utf-8"))
        ir_schema = json.loads(IR_SCHEMA.read_text(encoding="utf-8"))

        metadata_items = source_schema["properties"]["metadata"]["items"]
        resource_items = source_schema["properties"]["resources"]["items"]
        section_items = source_schema["properties"]["sections"]["items"]
        self.assertEqual(["label", "value"], metadata_items["required"])
        self.assertEqual(["label", "url"], resource_items["required"])
        self.assertEqual(["id", "title", "level", "blocks"], section_items["required"])
        self.assertGreaterEqual(
            len(section_items["properties"]["blocks"]["items"]["oneOf"]),
            5,
        )

        ir_blocks = ir_schema["properties"]["blocks"]
        self.assertEqual(1, ir_blocks["minItems"])
        self.assertGreaterEqual(len(ir_blocks["items"]["oneOf"]), 7)
        self.assertEqual(
            ["role_id", "mechanics", "colors"],
            ir_schema["$defs"]["style"]["required"],
        )

    def test_compile_cli_missing_or_invalid_input_fails_without_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "ir.json"
            receipt = root / "receipt.json"

            missing = subprocess.run(
                [
                    sys.executable,
                    str(COMPILE_CLI),
                    "--source",
                    str(root / "missing.json"),
                    "--design",
                    str(DESIGN),
                    "--output",
                    str(output),
                    "--receipt",
                    str(receipt),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(2, missing.returncode)
            self.assertIn("DF_INPUT_IO", missing.stderr)
            self.assertNotIn("Traceback", missing.stderr)

            invalid_source = root / "invalid.json"
            invalid_source.write_text("{not-json", encoding="utf-8")
            invalid = subprocess.run(
                [
                    sys.executable,
                    str(COMPILE_CLI),
                    "--source",
                    str(invalid_source),
                    "--design",
                    str(DESIGN),
                    "--output",
                    str(output),
                    "--receipt",
                    str(receipt),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(2, invalid.returncode)
            self.assertIn("DF_INPUT_JSON", invalid.stderr)
            self.assertNotIn("Traceback", invalid.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(receipt.exists())

    def test_compile_cli_receipt_staging_failure_leaves_no_ir_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "ir.json"
            blocked_parent = root / "not-a-directory"
            blocked_parent.write_text("blocking file", encoding="utf-8")
            receipt = blocked_parent / "receipt.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(COMPILE_CLI),
                    "--source",
                    str(SOURCE),
                    "--design",
                    str(DESIGN),
                    "--output",
                    str(output),
                    "--receipt",
                    str(receipt),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(2, completed.returncode)
            self.assertIn("DF_OUTPUT_IO", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertFalse(output.exists())

    def test_google_docs_cli_invalid_ir_json_is_typed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ir_path = root / "bad-ir.json"
            ir_path.write_text("{bad-json", encoding="utf-8")
            output = root / "plan.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ADAPTER_CLI),
                    "--ir",
                    str(ir_path),
                    "--required-feature",
                    "semantic_headings",
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(2, completed.returncode)
            self.assertIn("GDA_INPUT_JSON", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertFalse(output.exists())


    def test_google_docs_adapter_accepts_exact_declared_degradation(self):
        ir, _ = COMPILER.compile_document(self.source, self.design)
        policy = json.loads(DEGRADATION_POLICY.read_text(encoding="utf-8"))
        plan = ADAPTER.build_plan(
            ir,
            required_features=[
                "semantic_headings",
                "dynamic_page_fields",
            ],
            accepted_degradations=policy,
        )
        report = plan["capability_report"]
        self.assertEqual("READY_WITH_ACCEPTED_DEGRADATION", report["state"])
        self.assertEqual([], report["blocked_features"])
        self.assertEqual(
            ["dynamic_page_fields"],
            [item["feature"] for item in report["accepted_degradations"]],
        )
        self.assertEqual(1, len(plan["required_disclosures"]))
        self.assertEqual(
            "dynamic_page_fields",
            plan["required_disclosures"][0]["feature"],
        )

    def test_google_docs_adapter_rejects_stale_degradation_state(self):
        ir, _ = COMPILER.compile_document(self.source, self.design)
        policy = json.loads(DEGRADATION_POLICY.read_text(encoding="utf-8"))
        policy[0]["accepted_state"] = "STALE_OR_WRONG_PROVIDER_STATE"
        with self.assertRaises(ADAPTER.GoogleDocsAdapterError) as ctx:
            ADAPTER.build_plan(
                ir,
                required_features=["dynamic_page_fields"],
                accepted_degradations=policy,
            )
        self.assertEqual("GDA_UNSUPPORTED_FEATURE", ctx.exception.code)

    def test_google_docs_cli_emits_degraded_plan_with_disclosure(self):
        ir, _ = COMPILER.compile_document(self.source, self.design)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ir_path = root / "ir.json"
            output = root / "plan.json"
            ir_path.write_text(
                json.dumps(ir, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ADAPTER_CLI),
                    "--ir",
                    str(ir_path),
                    "--required-feature",
                    "semantic_headings",
                    "--required-feature",
                    "dynamic_page_fields",
                    "--degradation-policy",
                    str(DEGRADATION_POLICY),
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            plan = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                "READY_WITH_ACCEPTED_DEGRADATION",
                plan["capability_report"]["state"],
            )
            self.assertEqual(1, len(plan["required_disclosures"]))

    def test_core_has_no_hh_consumer_assumptions(self):
        source = COMPILER_PATH.read_text(encoding="utf-8").lower()
        adapter = ADAPTER_PATH.read_text(encoding="utf-8").lower()
        forbidden = ("nyc health", "northwell", "hh-metropolitan", "cc reader")
        self.assertFalse(any(item in source for item in forbidden))
        self.assertFalse(any(item in adapter for item in forbidden))


if __name__ == "__main__":
    unittest.main()
