"""AUTO-PD1: real subprocess fan-out and honest synthetic 100-lane capacity proof."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "capabilities/parallel-dispatch/run.py"
spec = importlib.util.spec_from_file_location("automation_parallel_dispatch", MODULE)
dispatch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dispatch
spec.loader.exec_module(dispatch)


def lane(n, *, sleep=0.025, resources=None, dependencies=None, exit_code=0):
    return {"id": f"work-{n:03d}",
            "argv": [sys.executable, "-c",
                     f"import time,sys;time.sleep({sleep});sys.exit({exit_code})"],
            "depends_on": dependencies or [], "exclusive_resources": resources or [],
            "timeout_seconds": 15}


def packet(items, cap=8):
    return {"schema": dispatch.SCHEMA, "max_concurrent": cap, "lanes": items}


class ParallelDispatchTests(unittest.TestCase):
    def test_100_admitted_and_real_concurrent_subprocesses(self):
        manifest = packet([lane(n) for n in range(100)], cap=8)
        preview = dispatch.run(manifest)
        self.assertEqual(preview["admission"], "VALIDATED_NOT_DISPATCHED")
        self.assertNotIn("observed_parallelism", preview)
        receipt = dispatch.run(manifest, execute=True)
        self.assertEqual(receipt["started_count"], 100)
        self.assertEqual(receipt["counts"]["SUCCEEDED"], 100)
        self.assertTrue(receipt["all_succeeded"])
        self.assertGreater(receipt["observed_peak_overlapping_processes"], 1)
        self.assertLessEqual(receipt["observed_peak_overlapping_processes"], 8)
        self.assertTrue(receipt["observed_parallelism"])
        self.assertNotIn("argv", json.dumps(receipt))
        self.assertIn("NOT 100 LLM agents", receipt["proof_ceiling"])

    def test_cap_one_means_no_parallelism(self):
        actual = dispatch.run(packet([lane(n) for n in range(4)], cap=1), execute=True)
        self.assertEqual(actual["observed_peak_overlapping_processes"], 1)
        self.assertFalse(actual["observed_parallelism"])

    def test_same_declared_mutation_resource_never_overlaps(self):
        jobs = [lane(n, resources=["shared-repository"]) for n in range(5)]
        actual = dispatch.run(packet(jobs, cap=5), execute=True)
        self.assertEqual(actual["counts"]["SUCCEEDED"], 5)
        self.assertEqual(actual["observed_peak_overlapping_processes"], 1)

    def test_independent_resource_groups_can_overlap(self):
        jobs = [lane(n, resources=[f"repo-{n}"]) for n in range(5)]
        actual = dispatch.run(packet(jobs, cap=5), execute=True)
        self.assertGreater(actual["observed_peak_overlapping_processes"], 1)

    def test_failed_parent_blocks_successor_but_independent_task_runs(self):
        tasks = [lane(0, exit_code=4), lane(1, dependencies=["work-000"]), lane(2)]
        actual = dispatch.run(packet(tasks, cap=3), execute=True)
        self.assertEqual(actual["counts"]["FAILED"], 1)
        self.assertEqual(actual["counts"]["BLOCKED_DEPENDENCY"], 1)
        self.assertEqual(actual["counts"]["SUCCEEDED"], 1)
        self.assertFalse(actual["all_succeeded"])

    def test_cycle_and_missing_dependency_fail_before_launch(self):
        m = packet([lane(0, dependencies=["work-001"]),
                    lane(1, dependencies=["work-000"])])
        with self.assertRaisesRegex(dispatch.DispatchAdmissionError, "cycle"):
            dispatch.run(m, execute=True)
        m = packet([lane(0, dependencies=["unknown"])])
        with self.assertRaisesRegex(dispatch.DispatchAdmissionError, "missing dependency"):
            dispatch.run(m, execute=True)

    def test_unknown_fields_dup_scope_and_shell_argv_are_denied(self):
        item = lane(0)
        item["mystery"] = "free-approval"
        with self.assertRaisesRegex(dispatch.DispatchAdmissionError, "structure"):
            dispatch.validate(packet([item]))
        m = packet([lane(0, resources=["duplicate", "duplicate"])])
        with self.assertRaisesRegex(dispatch.DispatchAdmissionError, "duplicate dependency"):
            dispatch.validate(m)
        m = packet([lane(0)])
        m["lanes"][0]["argv"] = ["powershell", "-NoProfile", "-Command", "Write-Host hi"]
        with self.assertRaisesRegex(dispatch.DispatchAdmissionError, "shell entrypoints"):
            dispatch.validate(m)

    def test_caps_and_boolean_lookalikes_fail_closed(self):
        for cap in (0, 101, True, "100"):
            with self.assertRaises(dispatch.DispatchAdmissionError):
                dispatch.validate(packet([lane(0)], cap=cap))
        with self.assertRaises(dispatch.DispatchAdmissionError):
            dispatch.validate(packet([lane(n) for n in range(1001)]))

    def test_no_implicit_execution_on_preview(self):
        item = lane(0, exit_code=1)
        result = dispatch.run(packet([item]))
        self.assertEqual(result["admission"], "VALIDATED_NOT_DISPATCHED")
        self.assertNotIn("counts", result)

    def test_missing_executable_records_spawn_failure(self):
        item = lane(0)
        item["argv"][0] = "missing-nonexistent-executable-8b9f7411"
        result = dispatch.run(packet([item]), execute=True)
        self.assertEqual(result["counts"]["SPAWN_FAILED"], 1)
        self.assertFalse(result["all_succeeded"])

    def test_no_stdout_or_stderr_leak(self):
        secret = "SYNTHETIC_CREDENTIAL_DO_NOT_LOG_675091"
        item = lane(0)
        item["argv"] = [sys.executable, "-c",
                        f"import sys;print({secret!r});print({secret!r},file=sys.stderr)"]
        result = dispatch.run(packet([item]), execute=True)
        self.assertEqual(result["counts"]["SUCCEEDED"], 1)
        self.assertNotIn(secret, json.dumps(result))

    def test_cli_preview_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            receipt = Path(folder) / "receipt.json"
            path.write_text(json.dumps(packet([lane(0)])), encoding="utf-8")
            import subprocess
            cmd = subprocess.run([sys.executable, str(MODULE), "--manifest", str(path),
                                  "--receipt", str(receipt)], text=True, capture_output=True)
            self.assertEqual(cmd.returncode, 0, cmd.stderr)
            record = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(record["admission"], "VALIDATED_NOT_DISPATCHED")


if __name__ == "__main__":
    unittest.main()
