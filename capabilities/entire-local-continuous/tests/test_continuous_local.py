"""Offline regressions for entire-local-continuous admission."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CAP = Path(__file__).resolve().parents[1]
CLI = CAP / "continuous_local.py"
CORE = CAP / "core" / "continuous_local.py"


def _load_core():
    spec = importlib.util.spec_from_file_location("elc_core", CORE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class ContinuousLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = _load_core()

    def test_capability_manifest(self):
        cap = json.loads((CAP / "capability.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(cap["capability_id"], "entire-local-continuous")
        self.assertEqual(cap["artifacts"]["contract"], "automation.entire-local-continuous/v1")

    def test_classify_not_setup(self):
        status = json.loads(
            (CAP / "fixtures/entire-status.not-setup.v1.json").read_text(encoding="utf-8")
        )
        result = self.core.classify_entire_status(status, entire_installed=True)
        self.assertEqual(result["adoption_state"], "DETECTED")
        self.assertFalse(result["enabled"])

    def test_classify_missing_binary(self):
        result = self.core.classify_entire_status({}, entire_installed=False)
        self.assertEqual(result["adoption_state"], "ENTIRE_MISSING")

    def test_classify_validated_local(self):
        status = json.loads(
            (CAP / "fixtures/entire-status.enabled-local.v1.json").read_text(encoding="utf-8")
        )
        result = self.core.classify_entire_status(
            status, entire_installed=True, doctor_ok=True, workflow_invariant=True
        )
        self.assertEqual(result["adoption_state"], "VALIDATED_LOCAL")

    def test_workflow_invariance(self):
        ok = self.core.check_workflow_invariance("DIGEST", "DIGEST")
        bad = self.core.check_workflow_invariance("DIGEST", "OTHER")
        absent = self.core.check_workflow_invariance(None, None)
        self.assertTrue(ok["pass"])
        self.assertFalse(bad["pass"])
        self.assertEqual(bad["blocker"], "WORKFLOW_DRIFT")
        self.assertTrue(absent["pass"])
        self.assertEqual(absent["before"], "ABSENT")

    def test_admit_good_proposal(self):
        proposal = json.loads(
            (CAP / "fixtures/afk-proposal.admitted.v1.json").read_text(encoding="utf-8")
        )
        result = self.core.admit_afk_continuous_loop(proposal)
        self.assertTrue(result["admitted"])
        self.assertEqual(result["violations"], [])

    def test_reject_console_actions_required_proposal(self):
        proposal = json.loads(
            (CAP / "fixtures/afk-proposal.console-rejected.v1.json").read_text(encoding="utf-8")
        )
        result = self.core.admit_afk_continuous_loop(proposal)
        self.assertFalse(result["admitted"])
        for code in (
            "SILENCE_BYPASS",
            "INTERACTIVE_SCHEDULED_CLASS",
            "CONSOLE_CRON_PROPOSED",
            "ACTIONS_REQUIRED_CLAIM",
            "REMOTE_PUSH_WITHOUT_POLICY",
        ):
            self.assertIn(code, result["violations"])

    def test_receipt_ready_gate(self):
        status = json.loads(
            (CAP / "fixtures/entire-status.enabled-local.v1.json").read_text(encoding="utf-8")
        )
        proposal = json.loads(
            (CAP / "fixtures/afk-proposal.admitted.v1.json").read_text(encoding="utf-8")
        )
        classification = self.core.classify_entire_status(
            status, entire_installed=True, doctor_ok=True, workflow_invariant=True
        )
        workflow = self.core.check_workflow_invariance("A", "A")
        admission = self.core.admit_afk_continuous_loop(proposal)
        receipt = self.core.build_receipt(
            repository="EndeavorEverlasting/Automation",
            classification=classification,
            workflow=workflow,
            admission=admission,
        )
        self.assertTrue(receipt["ready_for_afk_continuous"])
        self.assertEqual(receipt["blockers"], [])

    def test_cli_admit_exit_codes(self):
        good = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "admit-afk",
                "--proposal",
                str(CAP / "fixtures/afk-proposal.admitted.v1.json"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        bad = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "admit-afk",
                "--proposal",
                str(CAP / "fixtures/afk-proposal.console-rejected.v1.json"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(bad.returncode, 2, bad.stdout)

    def test_isolated_consumer_canary(self):
        """Copy only core module into a temp dir and import without Automation root."""
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "continuous_local.py"
            dest.write_text(CORE.read_text(encoding="utf-8"), encoding="utf-8")
            spec = importlib.util.spec_from_file_location("isolated_elc", dest)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            result = mod.admit_afk_continuous_loop(
                {
                    "job_id": "canary",
                    "silence_owner": "capabilities/windows-silent-scheduled-task",
                    "execution_class": "SILENT_BACKGROUND",
                    "scheduled_execute": "C:/Python/pythonw.exe",
                    "actions_policy": "OPTIONAL_UNCHANGED",
                    "entire_enable_flags": ["--local", "--skip-push-sessions"],
                    "may_disrupt_fullscreen": False,
                }
            )
            self.assertTrue(result["admitted"])


if __name__ == "__main__":
    unittest.main()
