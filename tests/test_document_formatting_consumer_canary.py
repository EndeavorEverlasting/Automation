from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "capabilities" / "document-formatting" / "plan.py"


class DocumentFormattingConsumerCanaryTests(unittest.TestCase):
    def profile(self):
        return {
            "schema_version": "document-formatting-consumer-profile/v1",
            "consumer_id": "isolated-canary",
            "profile_id": "docs-v1",
            "consumer_contract_ref": "consumer://isolated-canary/docs/v1",
            "archetypes": ["report"],
            "provider_adapters": [
                {
                    "provider_id": "provider-a",
                    "execution_environment": "CI_OR_REMOTE_RUNNER",
                    "required_features": ["headings"],
                }
            ],
            "visual_surfaces": [
                {
                    "surface_id": "provider-a-render",
                    "execution_environment": "CI_OR_REMOTE_RUNNER",
                    "provider_id": "provider-a",
                }
            ],
            "proof_policy": {
                "provider_readback_required": True,
                "prevent_proof_promotion": True,
                "lock_non_color_before_branding": False,
            },
            "branding": {"enabled": False},
        }

    def run_cli(self, profile):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            profile_path = root / "profile.json"
            output_path = root / "plan.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--profile",
                    str(profile_path),
                    "--output",
                    str(output_path),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            payload = (
                json.loads(output_path.read_text(encoding="utf-8"))
                if output_path.exists()
                else None
            )
            return completed, payload

    def test_isolated_consumer_uses_only_advertised_cli_and_profile(self):
        completed, payload = self.run_cli(self.profile())
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIsNotNone(payload)
        self.assertEqual("isolated-canary", payload["consumer_id"])
        self.assertEqual("document-formatting", payload["capability_id"])
        self.assertEqual(
            ["VISUAL_ACCEPTANCE::provider-a-render"],
            payload["terminal_dependencies"],
        )

    def test_isolated_consumer_fails_closed_on_branding_without_lock(self):
        profile = self.profile()
        profile["branding"]["enabled"] = True
        completed, payload = self.run_cli(profile)
        self.assertEqual(2, completed.returncode)
        self.assertIsNone(payload)
        self.assertIn(
            "branding requires proof_policy.lock_non_color_before_branding=true",
            completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
