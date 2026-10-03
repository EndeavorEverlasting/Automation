from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "path_receipt.py"
SPEC = importlib.util.spec_from_file_location("path_receipt", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)
CONTRACT = json.loads((ROOT / "harness/contracts/canonical-path.v1.json").read_text(encoding="utf-8"))


def fake_git(values):
    def run(_root, args):
        key = tuple(args)
        return values.get(key, (1, "", "missing fixture"))
    return run


class PathReceiptTests(unittest.TestCase):
    def test_verified_matching_checkout_is_canonical(self):
        root = Path("/tmp/Automation").resolve()
        git = fake_git({
            ("rev-parse", "--show-toplevel"): (0, str(root), ""),
            ("config", "--get", "remote.origin.url"): (0, "git@github.com:EndeavorEverlasting/Automation.git", ""),
            ("rev-parse", "HEAD"): (0, "abc123", ""),
        })
        receipt = MOD.build_receipt(root, CONTRACT, env={"SHELL": "/bin/bash"}, git_runner=git)
        self.assertEqual(receipt["path_input_receipt"]["development_state"], "CANONICAL_PROVED")
        self.assertEqual(receipt["path_input_receipt"]["normalized_origin_identity"], "EndeavorEverlasting/Automation")
        self.assertEqual(receipt["version_receipt"]["REMOTE_INTEGRATED"], "UNKNOWN")

    def test_wrong_remote_is_conflict_and_does_not_authorize_clone(self):
        root = Path("/tmp/not-automation").resolve()
        git = fake_git({
            ("rev-parse", "--show-toplevel"): (0, str(root), ""),
            ("config", "--get", "remote.origin.url"): (0, "https://github.com/example/other.git", ""),
            ("rev-parse", "HEAD"): (0, "abc123", ""),
        })
        receipt = MOD.build_receipt(root, CONTRACT, env={}, git_runner=git)
        self.assertEqual(receipt["path_input_receipt"]["development_state"], "CONFLICT")
        self.assertIn("Do not mutate or create another clone", receipt["safe_next_action"])

    def test_configured_dev_root_conflict_is_reported(self):
        root = Path("/tmp/Automation").resolve()
        git = fake_git({
            ("rev-parse", "--show-toplevel"): (0, str(root), ""),
            ("config", "--get", "remote.origin.url"): (0, "https://github.com/EndeavorEverlasting/Automation", ""),
            ("rev-parse", "HEAD"): (0, "abc123", ""),
        })
        receipt = MOD.build_receipt(
            root,
            CONTRACT,
            env={"AUTOMATION_DEV_ROOT": "/tmp/different"},
            git_runner=git,
        )
        self.assertEqual(receipt["path_input_receipt"]["development_state"], "CONFLICT")

    def test_unknown_production_state_blocks_production_mutation(self):
        root = Path("/tmp/Automation").resolve()
        git = fake_git({
            ("rev-parse", "--show-toplevel"): (0, str(root), ""),
            ("config", "--get", "remote.origin.url"): (0, "https://github.com/EndeavorEverlasting/Automation.git", ""),
            ("rev-parse", "HEAD"): (0, "abc123", ""),
        })
        receipt = MOD.build_receipt(
            root,
            CONTRACT,
            env={"AUTOMATION_PROD_ROOT": "/srv/automation"},
            git_runner=git,
        )
        path = receipt["path_input_receipt"]
        self.assertEqual(path["production_use_state"], "UNKNOWN")
        self.assertFalse(path["production_mutation_allowed"])

    def test_supported_remote_formats_normalize(self):
        cases = {
            "https://github.com/EndeavorEverlasting/Automation.git": "EndeavorEverlasting/Automation",
            "git@github.com:EndeavorEverlasting/Automation.git": "EndeavorEverlasting/Automation",
            "ssh://git@github.com/EndeavorEverlasting/Automation.git": "EndeavorEverlasting/Automation",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(MOD.normalize_repo_identity(raw), expected)


if __name__ == "__main__":
    unittest.main()
