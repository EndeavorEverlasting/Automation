"""Isolated consumer: only the advertised standalone gate file, no repo imports."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "capabilities/parallel-dispatch/receipt_gate.py"


class IsolatedConsumerTests(unittest.TestCase):
    def test_portable_import_and_fail_closed_without_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            shutil.copyfile(SOURCE, Path(directory) / "receipt_gate.py")
            script = """import sys
sys.path.insert(0, sys.argv[1])
import receipt_gate as gate
p = {"schema": gate.SCHEMA, "task_key": "job", "lane_id": "lane",
     "actor": "actor", "owner": "owner", "resource_id": "resource",
     "expected_head": "a"*40, "claim_token": "claim:1",
     "receipt_ref": "receipt:1", "max_age_seconds": 30}
try:
    gate.preflight(p, claim_reader=None, receipt_reader=None,
                   head_reader=None, now_epoch=1800000000)
except gate.AdmissionError:
    print("FAIL_CLOSED")
else:
    raise AssertionError("unexpected admission")
"""
            result = subprocess.run([sys.executable, "-I", "-c", script, directory],
                                    cwd=directory, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "FAIL_CLOSED")


if __name__ == "__main__":
    unittest.main()
