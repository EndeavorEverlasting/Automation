from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

CAP = Path(__file__).resolve().parents[1]
ROOT = CAP.parents[1]
CLI = CAP / "silent_cron.py"
FIXTURES = CAP / "fixtures"


class SilentCronCapabilityTests(unittest.TestCase):
    def test_capability_descriptor_points_at_entrypoints(self) -> None:
        cap = json.loads((CAP / "capability.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(cap["capability_id"], "windows-silent-scheduled-task")
        self.assertEqual(cap["status"], "CORE_IMPLEMENTED_WINDOWS_HOST")
        self.assertEqual(cap["production_use_path"], "UNDECLARED")
        self.assertTrue((ROOT / cap["entrypoint"]).is_file())
        self.assertTrue((ROOT / cap["entrypoints"]["cli"]).is_file())
        self.assertTrue((ROOT / cap["entrypoints"]["powershell"]).is_file())
        self.assertTrue((ROOT / cap["artifacts"]["registry_schema"]).is_file())
        self.assertTrue((ROOT / cap["artifacts"]["synthetic_registry"]).is_file())
        self.assertTrue((ROOT / "docs/WINDOWS_SILENT_SCHEDULED_TASK_SEAM_REVIEW.md").is_file())

    def test_registry_schema_const_matches_fixture(self) -> None:
        schema = json.loads(
            (CAP / "schemas/silent-cron-registry.v1.json").read_text(encoding="utf-8")
        )
        registry = json.loads(
            (FIXTURES / "registry.synthetic.v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            schema["properties"]["schema"]["const"],
            "automation.windows-silent-scheduled-task.registry/v1",
        )
        self.assertEqual(registry["schema"], schema["properties"]["schema"]["const"])
        self.assertEqual(registry["jobs"][0]["id"], "demo_tick")

    def test_classify_pythonw_fixture_is_silent(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "classify-fixture",
                "--fixture",
                str(FIXTURES / "schtasks-list.pythonw.fixture.txt"),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["silent_pythonw"])
        self.assertEqual(payload["status"], "READY")
        self.assertIn("pythonw.exe", payload["task_to_run"])

    def test_classify_console_python_fixture_is_noisy(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "classify-fixture",
                "--fixture",
                str(FIXTURES / "schtasks-list.console-python.fixture.txt"),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["silent_pythonw"])
        self.assertIn("py.exe", payload["task_to_run"])

    def test_render_contains_pythonw_and_hidden(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "render",
                "--registry",
                str(FIXTURES / "registry.synthetic.v1.json"),
                "--job-id",
                "demo_tick",
                "--repo-root",
                str(CAP),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["apply"])
        self.assertEqual(payload["repair_mode"], "render_only")
        ps = payload["powershell"]
        self.assertIn("pythonw", ps.lower())
        self.assertIn("-Hidden", ps)
        self.assertIn("Register-ScheduledTask", ps)
        self.assertIn("Automation-SilentCron-DemoTick", ps)
        self.assertIn("demo_tick.py", ps)

    def test_task_to_run_classifier_anchors_on_executable(self) -> None:
        sys.path.insert(0, str(CAP))
        from core.pythonw import task_to_run_is_silent_pythonw

        self.assertTrue(
            task_to_run_is_silent_pythonw(
                r'C:\Python\pythonw.exe "C:\repo\tick.py"'
            )
        )
        self.assertTrue(task_to_run_is_silent_pythonw(r'"C:\Python\pythonw.exe" tick.py'))
        self.assertFalse(
            task_to_run_is_silent_pythonw(r'C:\Python\python.exe "C:\repo\tick.py"')
        )
        self.assertFalse(
            task_to_run_is_silent_pythonw(
                r'C:\Python\python.exe "C:\weird\pythonw.exe\not-launcher.py"'
            )
        )

    def test_readme_admits_capability(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("windows-silent-scheduled-task", readme)
        self.assertIn("CORE_IMPLEMENTED_WINDOWS_HOST", readme)

    def test_registry_rejects_unsafe_values(self):
        import tempfile
        sys.path.insert(0, str(CAP))
        from core.registry import load_registry
        original = json.loads((FIXTURES / "registry.synthetic.v1.json").read_text(encoding="utf-8"))
        for field, value in (("interval_min", True), ("interval_min", 4.5),
                             ("interval_min", "15"), ("script", ""),
                             ("script", "../unsafe.py")):
            altered = json.loads(json.dumps(original))
            altered["jobs"][0][field] = value
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "reg.json"
                target.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_registry(target)
        altered = json.loads(json.dumps(original))
        altered["schema_version"] = altered.pop("schema")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "reg.json"
            target.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_registry(target)

    def test_render_single_quotes_and_no_destructive_unregister(self):
        sys.path.insert(0, str(CAP))
        from core.ensure import render_register_powershell
        job = json.loads((FIXTURES / "registry.synthetic.v1.json").read_text())["jobs"][0]
        job["task_name"] = "Owner's $Task"
        ps = render_register_powershell(job, pythonw=Path("C:/Python/pythonw.exe"),
                                         repo_root=CAP)
        self.assertIn("$task = 'Owner''s $Task'", ps)
        self.assertIn(" -Force | Out-Null", ps)
        self.assertNotIn("Unregister-ScheduledTask", ps)
        self.assertIn("-Hidden", ps)

    def test_render_has_no_installed_pythonw_dependency(self):
        from unittest.mock import patch
        import tempfile
        sys.path.insert(0, str(CAP))
        from core.ensure import ensure_job
        with patch("core.ensure.resolve_pythonw", side_effect=RuntimeError("must not probe host")):
            packet = ensure_job("demo_tick", registry=FIXTURES / "registry.synthetic.v1.json",
                                repo_root=CAP, apply=False)
        self.assertTrue(packet["ok"])
        self.assertFalse(packet["apply"])
        self.assertIn("pythonw.exe", packet["powershell"])

    def test_apply_transport_failure_is_a_typed_receipt(self):
        from unittest.mock import patch
        sys.path.insert(0, str(CAP))
        from core.ensure import ensure_job
        with patch("core.ensure.resolve_pythonw", return_value=Path("C:/Python/pythonw.exe")), \
             patch("core.ensure.discreet_run", side_effect=OSError("transport denied")):
            packet = ensure_job("demo_tick", registry=FIXTURES / "registry.synthetic.v1.json",
                                repo_root=CAP, apply=True)
        self.assertFalse(packet["ok"])
        self.assertEqual(packet["error"], "OSError")

    def test_render_requires_explicit_consumer_root(self):
        proc = subprocess.run([sys.executable, str(CLI), "render", "--registry",
                               str(FIXTURES / "registry.synthetic.v1.json"),
                               "--job-id", "demo_tick"], capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--repo-root is required", proc.stderr)


if __name__ == "__main__":
    unittest.main()
