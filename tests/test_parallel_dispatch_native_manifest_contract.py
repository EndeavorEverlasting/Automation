"""Integrated contract parity against canonical AUTO-PD1 run.py."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "capabilities/parallel-dispatch/run.py"
GATE = ROOT / "capabilities/parallel-dispatch/receipt_gate.py"


class NativeManifestContractTests(unittest.TestCase):
    def test_native_resource_regex_parity(self):
        # Integration is only meaningful when the real reusable gate is present.
        self.assertTrue(RUN.is_file(), "canonical dispatch validator missing")
        self.assertTrue(GATE.is_file(), "receipt gate must be integrated")
        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        run = load("native_parallel_dispatch_run", RUN)
        gate = load("parallel_dispatch_receipt_gate", GATE)
        self.assertEqual(run.ID.pattern, gate._NATIVE_RESOURCE_ID.pattern)
        for value in ["docs", "repo_main", "resource-1", "r" * 80]:
            self.assertTrue(run.ID.fullmatch(value))
            self.assertTrue(gate._NATIVE_RESOURCE_ID.fullmatch(value))
        for value in ["path:docs", "docs/subdir", "r" * 81, ""]:
            self.assertFalse(run.ID.fullmatch(value))
            self.assertFalse(gate._NATIVE_RESOURCE_ID.fullmatch(value))
