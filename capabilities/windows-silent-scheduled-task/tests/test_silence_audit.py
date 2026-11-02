"""Synthetic, provider-free silence audit and isolated-consumer portability tests."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CAP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAP))
from core.silence_audit import INPUT_SCHEMA, audit_evidence  # noqa: E402


def task(**overrides):
    data = {
        "id": "tick", "task_name": "Example-SilentTick",
        "task_to_run": '"C:\\Program Files\\Python\\pythonw.exe" "C:\\repo\\tick.py"',
        "hidden": True,
        "last_result": 2,
        "due_time": {
            "due_time_matched": True, "samples": 67, "console_title_hits": 0,
            "sync_process_samples": 21, "foreground_preserved": True,
        },
    }
    data.update(overrides)
    return data


def audit(*tasks):
    return audit_evidence({"schema": INPUT_SCHEMA, "tasks": list(tasks)})


class SilenceEvidenceTests(unittest.TestCase):
    def test_due_time_does_not_imply_certification_or_success(self):
        result = audit(task())
        row = result["tasks"][0]
        self.assertEqual(row["silence_state"], "DUE_TIME_OBSERVED")
        self.assertFalse(row["silence_review"])
        self.assertEqual(row["functional_state"], "NONZERO")
        self.assertEqual(result["summary"]["silent_certified_count"], 0)
        self.assertEqual(result["mutation"], "NONE")

    def test_hidden_powershell_requires_explicit_review(self):
        row = audit(task(task_to_run='"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -NoProfile -WindowStyle Hidden -File tick.ps1'))["tasks"][0]
        self.assertEqual(row["launcher_class"], "HIDDEN_POWERSHELL")
        self.assertEqual(row["silence_state"], "DUE_TIME_OBSERVED")
        self.assertTrue(row["silence_review"])

    def test_certification_requires_fullscreen_child_and_receipt(self):
        certified = {"child_processes": "CERTIFIED", "focus": "CERTIFIED", "focus_mode": "fullscreen", "proof_ref": "synthetic://receipt"}
        row = audit(task(certification=certified))["tasks"][0]
        self.assertEqual(row["silence_state"], "SILENT_CERTIFIED")
        self.assertFalse(row["silence_review"])
        certified["focus_mode"] = "foreground"
        row = audit(task(certification=certified))["tasks"][0]
        self.assertEqual(row["silence_state"], "DUE_TIME_OBSERVED")
        certified["focus_mode"] = "fullscreen"
        certified["proof_ref"] = ""
        self.assertNotEqual(audit(task(certification=certified))["tasks"][0]["silence_state"], "SILENT_CERTIFIED")

    def test_console_risk_cannot_be_laundered_by_successful_sample(self):
        full_cert = {"child_processes": "CERTIFIED", "focus": "CERTIFIED", "focus_mode": "fullscreen", "proof_ref": "synthetic://receipt"}
        row = audit(task(task_to_run='"C:\\Python\\python.exe" "C:\\repo\\pythonw.exe\\tick.py"', certification=full_cert))["tasks"][0]
        self.assertEqual(row["launcher_class"], "CONSOLE_RISK")
        self.assertEqual(row["silence_state"], "REVIEW")

    def test_console_hit_overrides_certification(self):
        full_cert = {"child_processes": "CERTIFIED", "focus": "CERTIFIED", "focus_mode": "fullscreen", "proof_ref": "synthetic://receipt"}
        obs = {"due_time_matched": True, "samples": 67, "console_title_hits": 1, "foreground_preserved": False}
        row = audit(task(certification=full_cert, due_time=obs))["tasks"][0]
        self.assertEqual(row["silence_state"], "FLASH_OBSERVED")
        self.assertTrue(row["silence_review"])

    def test_missing_hidden_setting_fails_layer(self):
        row = audit(task(hidden=False))["tasks"][0]
        self.assertFalse(row["launcher_compliant"])
        self.assertTrue(row["silence_review"])

    def test_unknown_launcher_and_unquoted_pythonw_argument(self):
        row = audit(task(task_to_run='wscript.exe C:\\tools\\pythonw.exe\\tick.py'))["tasks"][0]
        self.assertEqual(row["launcher_class"], "UNKNOWN")
        self.assertTrue(row["silence_review"])

    def test_declared_node_still_needs_child_and_focus_proof(self):
        row = audit(task(task_to_run='node.exe app.js', launcher_no_window=True))["tasks"][0]
        self.assertEqual(row["launcher_class"], "DECLARED_WINDOWLESS_NODE")
        self.assertTrue(row["silence_review"])

    def test_unknown_functional_result_is_distinct(self):
        row = audit(task(last_result="unknown"))["tasks"][0]
        self.assertEqual(row["functional_state"], "UNKNOWN")
        self.assertEqual(row["silence_state"], "DUE_TIME_OBSERVED")

    def test_malformed_and_duplicate_inputs_fail_closed(self):
        for change in [dict(hidden="true"), dict(due_time={"due_time_matched": True, "samples": -1, "console_title_hits": 0, "foreground_preserved": True}), dict(due_time={"due_time_matched": True, "samples": 1, "console_title_hits": 2, "foreground_preserved": True})]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                audit(task(**change))
        with self.assertRaises(ValueError):
            audit(task(), task())
        with self.assertRaises(ValueError):
            audit_evidence({"schema": "wrong", "tasks": [task()]})

    def test_isolated_consumer_only_needs_published_module(self):
        with tempfile.TemporaryDirectory() as temp:
            source = CAP / "core" / "silence_audit.py"
            copy = Path(temp) / "silence_audit.py"
            shutil.copyfile(source, copy)
            script = "import silence_audit; print(silence_audit.INPUT_SCHEMA)"
            proc = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, " + repr(temp) + "); " + script], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), INPUT_SCHEMA)


if __name__ == "__main__":
    unittest.main()
