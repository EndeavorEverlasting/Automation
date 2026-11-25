"""Regression gates for exact tracked-file ownership and semantic parity."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("feature_ontology", ROOT / "scripts/validate_feature_ontology.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class FeatureOntologyTests(unittest.TestCase):
    def test_repository_has_zero_unmapped_or_stale_paths(self):
        receipt = validator.validate(ROOT)
        self.assertTrue(receipt["ok"], receipt)
        self.assertGreater(receipt["tracked"], 0)

    def test_real_git_index_add_delete_and_projection_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
            git("init")
            manifest = {"schema_version": "feature-ontology/v1", "coverage": "all-git-index-paths",
                        "features": [{"id": "sample", "summary": "Sample ownership.",
                        "files": [{"path": p, "role": "source" if p.endswith(".py") else "documentation"}
                                  for p in (validator.ONTOLOGY, validator.PROJECTION, "source.py")]}]}
            (root / validator.ONTOLOGY).parent.mkdir(parents=True)
            (root / validator.ONTOLOGY).write_text(json.dumps(manifest), encoding="utf-8")
            (root / validator.PROJECTION).write_text(validator.render(manifest), encoding="utf-8")
            (root / "source.py").write_text("pass\n", encoding="utf-8")
            git("add", ".")
            self.assertTrue(validator.validate(root)["ok"])
            (root / "new.py").write_text("pass\n", encoding="utf-8")
            git("add", "new.py")
            result = validator.validate(root)
            self.assertFalse(result["ok"])
            self.assertEqual(result["unmapped"], ["new.py"])
            git("rm", "--cached", "-f", "source.py")
            self.assertEqual(validator.validate(root)["stale"], ["source.py"])
            (root / validator.PROJECTION).write_text("stale\n", encoding="utf-8")
            self.assertFalse(validator.validate(root)["projection_matches"])
            output = subprocess.run(["python", str(ROOT / "scripts/validate_feature_ontology.py"), "--root", str(root)],
                                    capture_output=True, text=True)
            self.assertEqual(output.returncode, 1)

    def test_duplicate_owner_and_wildcards_fail_closed(self):
        ontology = validator.load(ROOT)
        for mutation in ("duplicate", "wildcard", "empty", "unknown-role"):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(ontology)
                feature = bad["features"][0]
                if mutation == "duplicate":
                    feature["files"].append(copy.deepcopy(feature["files"][0]))
                elif mutation == "wildcard":
                    feature["files"][0]["path"] = "capabilities/**"
                elif mutation == "empty":
                    feature["files"] = []
                else:
                    feature["files"][0]["role"] = "unknown"
                with self.assertRaises(ValueError):
                    validator.inspect(bad, set())

    def test_duplicate_json_keys_fail(self):
        with self.assertRaises(ValueError):
            json.loads('{"path":"a","path":"b"}', object_pairs_hook=validator.reject_duplicate_keys)


if __name__ == "__main__":
    unittest.main()
