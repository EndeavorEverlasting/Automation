from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "capabilities" / "local-agent-readiness"
sys.path.insert(0, str(CAP))

from core.readiness import (  # noqa: E402
    ReadinessError,
    agent_profile_digest,
    assess_readiness,
    load_profile,
)


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


class LocalAgentReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.seed = base / "seed"
        self.remote = base / "remote.git"
        self.work = base / "work"
        self.profile_path = base / "profile.json"

        self.seed.mkdir()
        git(self.seed, "init")
        git(self.seed, "config", "user.name", "Readiness Fixture")
        git(self.seed, "config", "user.email", "fixture@example.invalid")
        git(self.seed, "checkout", "-b", "main")

        files = {
            "AGENTS.md": "shared contract\n",
            ".cursor/hooks.json": "{}\n",
            ".cursor/hooks/p07.py": "print('cursor fixture')\n",
            "opencode.json": "{}\n",
            ".opencode/config.json": "{}\n",
            "src/app.py": "print('app')\n",
        }
        for rel, text in files.items():
            path = self.seed / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        git(self.seed, "add", ".")
        git(self.seed, "commit", "-m", "initial agent projections")

        git(base, "init", "--bare", str(self.remote))
        git(self.seed, "remote", "add", "origin", str(self.remote))
        git(self.seed, "push", "-u", "origin", "main")
        git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")

        git(base, "clone", "-b", "main", str(self.remote), str(self.work))
        git(self.work, "config", "user.name", "Readiness Worktree")
        git(self.work, "config", "user.email", "fixture@example.invalid")

        self.profile = {
            "schema_version": "local-agent-readiness-profile/v1",
            "repository": {
                "remote": "origin",
                "baseline_branch": "main",
                "remote_identity": None,
            },
            "projection_sets": [
                {"id": "shared", "paths": ["AGENTS.md"]},
                {
                    "id": "cursor",
                    "paths": [".cursor/hooks.json", ".cursor/hooks"],
                },
                {
                    "id": "opencode",
                    "paths": ["opencode.json", ".opencode"],
                },
            ],
            "agents": [
                {
                    "agent_id": "cursor",
                    "projection_sets": ["shared", "cursor"],
                    "required_gates": [
                        "REPOSITORY_CHECKOUT_CURRENT",
                        "AGENT_PROJECTION_MATCHES_BASELINE",
                        "LOCAL_AGENT_RUNTIME_VERIFIED",
                        "REMOTE_WRITE_VERIFIED",
                        "ACTUAL_PUSH_PROVEN",
                    ],
                    "runtime_claims_required": [
                        "PROJECT_CONFIGURATION_LOADED",
                        "HOOK_TRANSPORT_VERIFIED",
                    ],
                },
                {
                    "agent_id": "opencode",
                    "projection_sets": ["shared", "opencode"],
                    "required_gates": [
                        "REPOSITORY_CHECKOUT_CURRENT",
                        "AGENT_PROJECTION_MATCHES_BASELINE",
                        "LOCAL_AGENT_RUNTIME_VERIFIED",
                    ],
                    "runtime_claims_required": ["PROJECT_CONFIGURATION_LOADED"],
                },
            ],
            "remote_write": {
                "dry_run_namespace": "refs/heads/agent-readiness-canary"
            },
        }
        self.profile_path.write_text(
            json.dumps(self.profile, indent=2) + "\n",
            encoding="utf-8",
        )
        self.profile = load_profile(self.profile_path)

    def head(self, root: Path | None = None) -> str:
        return git(root or self.work, "rev-parse", "HEAD").stdout.strip()

    def assess(
        self,
        agent: str,
        *,
        runtime_observation: Path | None = None,
        probe_remote_write: bool = False,
        actual_push_ref: str | None = None,
    ) -> dict:
        return assess_readiness(
            self.work,
            self.profile,
            agent_id=agent,
            refresh_remote=True,
            runtime_observation=runtime_observation,
            probe_remote_write=probe_remote_write,
            actual_push_ref=actual_push_ref,
        )

    def write_observation(
        self,
        agent: str,
        path: Path,
        *,
        floor_sha: str | None = None,
        profile_digest: str | None = None,
    ) -> Path:
        required = next(
            item["runtime_claims_required"]
            for item in self.profile["agents"]
            if item["agent_id"] == agent
        )
        value = {
            "schema_version": "local-agent-runtime-observation/v1",
            "agent_id": agent,
            "status": "PASS",
            "proof_class": "LIVE_HOST_OBSERVATION",
            "observed_at": "2026-10-04T00:00:00Z",
            "floor_sha": floor_sha or self.head(),
            "agent_profile_sha256": (
                profile_digest or agent_profile_digest(self.profile, agent)
            ),
            "host_version": "synthetic-1",
            "claims": [
                {
                    "id": claim,
                    "state": "PASS",
                    "evidence_refs": [f"synthetic:{agent}:{claim.lower()}"],
                }
                for claim in required
            ],
            "raw_private_content_persisted": False,
            "proof_ceiling": "Synthetic isolated-consumer live-host shape only.",
        }
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def advance_remote(self, rel: str, text: str) -> str:
        target = self.seed / rel
        target.write_text(target.read_text(encoding="utf-8") + text, encoding="utf-8")
        git(self.seed, "add", rel)
        git(self.seed, "commit", "-m", f"advance {rel}")
        git(self.seed, "push", "origin", "main")
        return self.head(self.seed)

    def update_work(self) -> None:
        git(self.work, "fetch", "origin", "main")
        git(self.work, "reset", "--hard", "origin/main")

    def test_stale_checkout_and_projection_fail_before_host_blame(self) -> None:
        self.advance_remote(".cursor/hooks/p07.py", "# remote repair\n")
        receipt = self.assess("cursor")

        self.assertEqual(
            receipt["gates"]["REPOSITORY_CHECKOUT_CURRENT"]["state"], "FAIL"
        )
        self.assertEqual(
            receipt["gates"]["AGENT_PROJECTION_MATCHES_BASELINE"]["state"], "FAIL"
        )
        self.assertEqual(receipt["diagnosis"], "STALE_LOCAL_AGENT_PROJECTION")
        self.assertEqual(
            receipt["gates"]["LOCAL_AGENT_RUNTIME_VERIFIED"]["state"], "NOT_RUN"
        )

    def test_cursor_only_drift_does_not_contaminate_opencode(self) -> None:
        target = self.work / ".cursor/hooks/p07.py"
        target.write_text(target.read_text(encoding="utf-8") + "# local cursor work\n", encoding="utf-8")
        git(self.work, "add", ".cursor/hooks/p07.py")
        git(self.work, "commit", "-m", "cursor-only projector change")

        cursor = self.assess("cursor")
        opencode = self.assess("opencode")

        self.assertEqual(
            cursor["gates"]["AGENT_PROJECTION_MATCHES_BASELINE"]["state"], "FAIL"
        )
        self.assertEqual(
            opencode["gates"]["AGENT_PROJECTION_MATCHES_BASELINE"]["state"], "PASS"
        )
        self.assertEqual(
            opencode["gates"]["REPOSITORY_CHECKOUT_CURRENT"]["state"], "PASS"
        )

    def test_shared_projection_change_invalidates_both_agents(self) -> None:
        target = self.work / "AGENTS.md"
        target.write_text(target.read_text(encoding="utf-8") + "shared change\n", encoding="utf-8")
        git(self.work, "add", "AGENTS.md")
        git(self.work, "commit", "-m", "shared projection change")

        for agent in ("cursor", "opencode"):
            receipt = self.assess(agent)
            self.assertEqual(
                receipt["gates"]["AGENT_PROJECTION_MATCHES_BASELINE"]["state"],
                "FAIL",
            )

    def test_unrelated_code_change_does_not_invalidate_projection(self) -> None:
        target = self.work / "src/app.py"
        target.write_text(target.read_text(encoding="utf-8") + "print('feature')\n", encoding="utf-8")
        git(self.work, "add", "src/app.py")
        git(self.work, "commit", "-m", "ordinary feature work")

        for agent in ("cursor", "opencode"):
            receipt = self.assess(agent)
            self.assertEqual(
                receipt["gates"]["REPOSITORY_CHECKOUT_CURRENT"]["state"], "PASS"
            )
            self.assertEqual(
                receipt["gates"]["AGENT_PROJECTION_MATCHES_BASELINE"]["state"],
                "PASS",
            )

    def test_untracked_shadow_inside_declared_projection_is_visible(self) -> None:
        shadow = self.work / ".cursor/hooks/local-only.py"
        shadow.write_text("print('shadow')\n", encoding="utf-8")

        cursor = self.assess("cursor")
        opencode = self.assess("opencode")

        self.assertEqual(
            cursor["gates"]["AGENT_PROJECTION_MATCHES_BASELINE"]["state"], "FAIL"
        )
        self.assertIn(
            ".cursor/hooks/local-only.py",
            cursor["gates"]["AGENT_PROJECTION_MATCHES_BASELINE"]["evidence"]["changed_paths"],
        )
        self.assertEqual(
            opencode["gates"]["AGENT_PROJECTION_MATCHES_BASELINE"]["state"], "PASS"
        )

    def test_live_observation_is_agent_specific_and_profile_bound(self) -> None:
        cursor_obs = self.write_observation("cursor", self.work / "cursor-observation.json")

        cursor = self.assess("cursor", runtime_observation=cursor_obs)
        opencode = self.assess("opencode", runtime_observation=cursor_obs)

        self.assertEqual(
            cursor["gates"]["LOCAL_AGENT_RUNTIME_VERIFIED"]["state"], "PASS"
        )
        self.assertEqual(
            opencode["gates"]["LOCAL_AGENT_RUNTIME_VERIFIED"]["state"], "FAIL"
        )

        wrong_digest = self.write_observation(
            "cursor",
            self.work / "wrong-profile.json",
            profile_digest="0" * 64,
        )
        mismatched = self.assess("cursor", runtime_observation=wrong_digest)
        self.assertEqual(
            mismatched["gates"]["LOCAL_AGENT_RUNTIME_VERIFIED"]["state"], "FAIL"
        )

    def test_projection_change_after_observation_invalidates_live_proof(self) -> None:
        floor = self.head()
        observation = self.write_observation(
            "cursor", self.work / "cursor-observation.json", floor_sha=floor
        )
        target = self.work / ".cursor/hooks/p07.py"
        target.write_text(target.read_text(encoding="utf-8") + "# after observation\n", encoding="utf-8")
        git(self.work, "add", ".cursor/hooks/p07.py")
        git(self.work, "commit", "-m", "change projector after observation")

        receipt = self.assess("cursor", runtime_observation=observation)
        self.assertEqual(
            receipt["gates"]["LOCAL_AGENT_RUNTIME_VERIFIED"]["state"], "FAIL"
        )

    def test_opencode_can_be_ready_without_push_gates_when_profile_does_not_require_them(self) -> None:
        observation = self.write_observation(
            "opencode", self.work / "opencode-observation.json"
        )
        receipt = self.assess("opencode", runtime_observation=observation)

        self.assertEqual(receipt["state"], "READY")
        self.assertEqual(receipt["diagnosis"], "LOCAL_AGENT_READY")
        self.assertEqual(receipt["gates"]["REMOTE_WRITE_VERIFIED"]["state"], "NOT_RUN")
        self.assertEqual(receipt["gates"]["ACTUAL_PUSH_PROVEN"]["state"], "NOT_RUN")

    def test_cursor_dry_run_and_actual_push_remain_separate_proofs(self) -> None:
        observation = self.write_observation(
            "cursor", self.work / "cursor-observation.json"
        )
        dry = self.assess(
            "cursor",
            runtime_observation=observation,
            probe_remote_write=True,
        )
        self.assertEqual(dry["gates"]["REMOTE_WRITE_VERIFIED"]["state"], "PASS")
        self.assertEqual(dry["gates"]["ACTUAL_PUSH_PROVEN"]["state"], "NOT_RUN")
        self.assertEqual(dry["state"], "NOT_READY")
        self.assertEqual(dry["diagnosis"], "ACTUAL_PUSH_NOT_PROVEN")

        remote_ref = "refs/heads/readiness-proof"
        git(self.work, "push", "origin", f"HEAD:{remote_ref}")
        full = self.assess(
            "cursor",
            runtime_observation=observation,
            probe_remote_write=True,
            actual_push_ref=remote_ref,
        )
        self.assertEqual(full["gates"]["ACTUAL_PUSH_PROVEN"]["state"], "PASS")
        self.assertEqual(full["state"], "READY")
        self.assertEqual(full["diagnosis"], "LOCAL_AGENT_READY")

    def test_assessment_does_not_modify_worktree_configuration(self) -> None:
        local_note = self.work / "local-note.txt"
        local_note.write_text("preserve me\n", encoding="utf-8")
        before = git(self.work, "status", "--porcelain").stdout

        self.assess("opencode")

        after = git(self.work, "status", "--porcelain").stdout
        self.assertEqual(before, after)
        self.assertEqual(local_note.read_text(encoding="utf-8"), "preserve me\n")

    def test_unsafe_projection_path_is_rejected(self) -> None:
        broken = json.loads(self.profile_path.read_text(encoding="utf-8"))
        broken["projection_sets"][0]["paths"] = ["../outside"]
        path = self.profile_path.parent / "broken.json"
        path.write_text(json.dumps(broken), encoding="utf-8")
        with self.assertRaises(ReadinessError):
            load_profile(path)


if __name__ == "__main__":
    unittest.main()
