from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from shutil import which
from typing import Optional

CAP = Path(__file__).resolve().parents[1]
ROOT = CAP.parents[1]
MANIFEST = CAP / "ghidra-bootstrap.manifest.json"
SCHEMA = CAP / "schemas" / "manifest.v1.json"


class GhidraBootstrapTests(unittest.TestCase):
    def test_manifest_matches_schema_constants(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "automation.ghidra-bootstrap.v1")
        self.assertEqual(data["capability_id"], "ghidra-bootstrap")
        self.assertEqual(data["agreement"]["property"], "USER_AGREEMENT")
        self.assertEqual(data["agreement"]["accepted_value"], "ACCEPT")
        self.assertRegex(data["ghidra"]["sha256"], r"^[a-fA-F0-9]{64}$")
        self.assertTrue(data["ghidra"]["url"].startswith("https://"))
        self.assertEqual(schema["properties"]["schema"]["const"], data["schema"])

    def test_capability_descriptor_points_at_entrypoints(self):
        cap = json.loads((CAP / "capability.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(cap["capability_id"], "ghidra-bootstrap")
        self.assertTrue((ROOT / cap["entrypoints"]["cmd"]).is_file())
        self.assertTrue((ROOT / cap["entrypoints"]["root_shim"]).is_file())
        self.assertTrue((ROOT / cap["core_owner"]).is_file())
        self.assertTrue((ROOT / cap["artifacts"]["manifest"]).is_file())

    def test_synthetic_agreement_prove_script(self):
        prove = CAP / "Prove-GhidraBootstrap.ps1"
        ps_exe = which("pwsh") or which("powershell")
        self.assertIsNotNone(ps_exe, "pwsh/powershell required for synthetic prove")
        proc = subprocess.run(
            [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(prove)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        self.assertIn("OBSERVED_AGREEMENT_SEEDED_SYNTHETIC", proc.stdout)


if __name__ == "__main__":
    unittest.main()
