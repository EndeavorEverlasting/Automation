from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CAP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAP))
from core.silent_background import CONTRACT, SilentBackground, _decision, _windows_options


class SilentBackgroundClassTests(unittest.TestCase):
    def test_child_console_gate_defer_interactive_no_spawn(self):
        with tempfile.TemporaryDirectory() as temp, patch("core.silent_background.subprocess.run") as run:
            guard = SilentBackground(job_id="alpha.tick", receipt_dir=Path(temp))
            for command in (["msiexec.exe", "/i", "package.msi"], ["winget", "upgrade", "app"],
                            ["chrome.exe", "example.org"], ["cmd.exe", "/c", "start", "app"]):
                receipt = guard.execute(command)
                self.assertEqual(receipt["status"], "DEFERRED_INTERACTION")
                self.assertTrue(Path(receipt["receipt_path"]).is_file())
            run.assert_not_called()

    def test_defer_unregistered_executable_and_shell_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            guard = SilentBackground(job_id="tick", receipt_dir=Path(temp))
            row = guard.execute(["unknown.exe", "--quiet"])
            self.assertEqual(row["reason_code"], "EXECUTABLE_NOT_ADMITTED")
            with self.assertRaisesRegex(ValueError, "shell=True"):
                guard.execute(["python.exe", "tick.py"], shell=True)

    def test_powershell_unattended_gates(self):
        permitted = frozenset()
        self.assertEqual(_decision(["pwsh.exe", "-File", "tick.ps1"], approved_tools=permitted),
                         "POWERSHELL_REQUIRES_NONINTERACTIVE")
        self.assertEqual(_decision(["pwsh.exe", "-NonInteractive", "-File", "tick.ps1"], approved_tools=permitted),
                         "POWERSHELL_REQUIRES_NOPROFILE")
        self.assertEqual(_decision(["pwsh.exe", "-NonInteractive", "-NoProfile", "-Command", "Read-Host"], approved_tools=permitted),
                         "POWERSHELL_INTERACTIVE_ACTION")
        self.assertIsNone(_decision(["pwsh.exe", "-NonInteractive", "-NoProfile", "-File", "tick.ps1"], approved_tools=permitted))

    def test_silent_run_receipt_distinguishes_functional_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            guard = SilentBackground(job_id="jobs.tick", receipt_dir=Path(temp), approved_tools=[sys.executable])
            row = guard.execute([sys.executable, "-c", "import sys; sys.exit(2)"])
            self.assertEqual(row["status"], "NONZERO")
            self.assertEqual(row["returncode"], 2)
            self.assertEqual(row["schema"], CONTRACT)
            self.assertEqual(json.loads(Path(row["receipt_path"]).read_text())["status"], "NONZERO")
            self.assertNotIn("sys.exit(2)", Path(row["receipt_path"]).read_text())
            self.assertFalse(row["mutated_scheduler"])

    def test_silent_success_is_not_fullscreen_certification(self):
        with tempfile.TemporaryDirectory() as temp:
            row = SilentBackground(job_id="tick", receipt_dir=Path(temp),
                                   approved_tools=[sys.executable]).execute(
                [sys.executable, "-c", "print('ok')"])
            self.assertEqual(row["status"], "SUCCEEDED")
            self.assertIn("NOT_DESCENDANT_OR_FULLSCREEN_CERTIFIED", row["proof_ceiling"])

    def test_no_window_win32_options_keep_other_flags(self):
        class Info:
            def __init__(self):
                self.dwFlags = 0
                self.wShowWindow = 1
        with patch("core.silent_background.sys.platform", "win32"), \
             patch("core.silent_background.subprocess.STARTUPINFO", Info, create=True), \
             patch("core.silent_background.subprocess.STARTF_USESHOWWINDOW", 1, create=True), \
             patch("core.silent_background.subprocess.SW_HIDE", 0, create=True):
            o = _windows_options({"creationflags": 0x100})
            self.assertEqual(o["creationflags"] & 0x08000000, 0x08000000)
            self.assertTrue(o["startupinfo"].dwFlags & 1)
            self.assertEqual(o["startupinfo"].wShowWindow, 0)

    def test_bad_id_fails_closed(self):
        for value in ("../bad", "", "space in id", "."):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SilentBackground(job_id=value)

    def test_spawn_returns_unproved_pid_and_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            guard = SilentBackground(job_id="tick", receipt_dir=Path(temp), approved_tools=[sys.executable])
            row = guard.execute([sys.executable, "-c", "pass"], wait=False)
            self.assertEqual(row["status"], "SPAWNED_NOT_CERTIFIED")
            self.assertIsInstance(row["pid"], int)

    def test_isolated_consumer_copy_has_no_automation_source_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            shutil.copyfile(CAP / "core" / "silent_background.py", Path(temp) / "silent_background.py")
            p = subprocess.run([sys.executable, "-I", "-c",
                                "import sys; sys.path.insert(0, " + repr(temp) + "); "
                                "import silent_background; print(silent_background.CONTRACT)"],
                               capture_output=True, text=True, check=False)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout.strip(), CONTRACT)

    def test_disallow_override_of_io_streams(self):
        with tempfile.TemporaryDirectory() as temp:
            guard = SilentBackground(job_id="tick", receipt_dir=Path(temp))
            with self.assertRaisesRegex(ValueError, "std streams"):
                guard.execute(["git", "status"], stdout=subprocess.PIPE)


    def test_explicit_interactive_class_preserves_inherited_io(self):
        with tempfile.TemporaryDirectory() as temp, patch("core.silent_background.subprocess.run") as run:
            run.return_value.returncode = 0
            guard = SilentBackground(job_id="manual", receipt_dir=Path(temp))
            receipt = guard.execute(["unknown-gui.exe"], execution_class="INTERACTIVE")
            self.assertEqual(receipt["status"], "SUCCEEDED")
            options = run.call_args.kwargs
            self.assertNotIn("stdin", options)
            self.assertNotIn("capture_output", options)
            self.assertNotIn("creationflags", options)
            self.assertEqual(receipt["execution_class"], "INTERACTIVE")

    def test_windows_new_console_conflict_is_rejected(self):
        class Info:
            def __init__(self):
                self.dwFlags = 0
                self.wShowWindow = 1
        with patch("core.silent_background.sys.platform", "win32"), \
             patch("core.silent_background.subprocess.STARTUPINFO", Info, create=True):
            with self.assertRaisesRegex(ValueError, "conflict"):
                _windows_options({"creationflags": 0x00000010})
            with self.assertRaisesRegex(ValueError, "conflict"):
                _windows_options({"creationflags": 0x00000008})


    def test_missing_private_receipt_blocks_background_before_spawn(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch("core.silent_background._persist", side_effect=PermissionError("no receipt")) as persist, \
             patch("core.silent_background.subprocess.run") as run:
            guard = SilentBackground(job_id="tick", receipt_dir=Path(temp))
            with self.assertRaises(PermissionError):
                guard.execute(["git", "status"])
            persist.assert_called_once()
            run.assert_not_called()

    def test_interactive_ui_does_not_need_background_receipt_store(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch("core.silent_background._persist", side_effect=PermissionError("no receipt")), \
             patch("core.silent_background.subprocess.run") as run:
            run.return_value.returncode = 0
            result = SilentBackground(job_id="manual", receipt_dir=Path(temp)).execute(
                ["my-app.exe"], execution_class="INTERACTIVE"
            )
            self.assertEqual(result["status"], "SUCCEEDED")
            self.assertIsNone(result["receipt_path"])
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
