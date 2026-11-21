"""Behavioral and adversarial tests for the reusable repository-handoff seam."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repository_handoff", ROOT / "handoff.py")
assert SPEC is not None and SPEC.loader is not None
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)
FIXTURE = ROOT / "fixtures/synthetic-handoff.v1.json"


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               check=True)
    return completed.stdout.strip()


def repo_at(directory: Path, name: str):
    root = directory / name
    root.mkdir()
    run_git(root, "init", "-b", "main")
    run_git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "--allow-empty", "-m", "synthetic baseline")
    run_git(root, "checkout", "-b", "feature/portable-handoff-canary")
    return root


def packet_for(root: Path, *, repository_id="example-org/example-service",
               canonical_path="harness/handoffs/CURRENT.md"):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["repository_id"] = repository_id
    data["canonical_path"] = canonical_path
    data["baseline_sha"] = run_git(root, "rev-parse", "HEAD")
    return data


class RepositoryHandoffTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.repo = repo_at(self.root, "consumer-one")
        self.packet = packet_for(self.repo)

    def test_synthetic_packet_is_valid_but_not_remote_proof(self):
        p = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIs(handoff.validate(p), p)
        rendered = handoff.render(p)
        self.assertIn("Synthetic fixture only", rendered)
        self.assertIn("Do not ask the operator to download", rendered)
        self.assertNotIn("TRIFECTA_AGENT_SESSION_ID", rendered)

    def test_two_isolated_consumers_do_not_need_parallaxport_topology(self):
        second = repo_at(self.root, "consumer-two")
        second_packet = packet_for(
            second, repository_id="other-team/other-product",
            canonical_path="docs/agents/CONTINUATION.md")
        for root, packet in ((self.repo, self.packet), (second, second_packet)):
            receipt = handoff.write(root, packet)
            self.assertEqual(receipt["result"], "WRITTEN_WORKTREE_NOT_COMMITTED")
            self.assertEqual(receipt["git_head_sha"], packet["baseline_sha"])
            self.assertEqual((root / packet["canonical_path"]).read_text(encoding="utf-8"),
                             handoff.render(packet))
            target, head = handoff.owned_destination(root, packet)
            self.assertEqual(head, packet["baseline_sha"])
            self.assertEqual(target.read_bytes(), handoff.render(packet).encode())
            self.assertNotIn("ParallaxPort", target.read_text(encoding="utf-8"))
            self.assertNotIn("TokenCorridor", target.read_text(encoding="utf-8"))
        self.assertFalse((self.repo / "docs/agents/CONTINUATION.md").exists())

    def test_existing_handoff_requires_exact_old_sha256(self):
        first = handoff.write(self.repo, self.packet)
        with self.assertRaisesRegex(handoff.HandoffError, "expected_sha256"):
            handoff.write(self.repo, self.packet)
        with self.assertRaisesRegex(handoff.HandoffError, "preimage"):
            handoff.write(self.repo, self.packet, expected_sha256="0" * 64)
        revised = copy.deepcopy(self.packet)
        revised["accomplished"].append("Another bounded change")
        second = handoff.write(self.repo, revised, expected_sha256=first["sha256"])
        self.assertNotEqual(first["sha256"], second["sha256"])
        self.assertEqual((self.repo / revised["canonical_path"]).read_text(encoding="utf-8"),
                         handoff.render(revised))

    def test_stale_head_and_branch_fail_closed(self):
        old_head = self.packet["baseline_sha"]
        run_git(self.repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "--allow-empty", "-m", "other agent advance")
        with self.assertRaisesRegex(handoff.HandoffError, "stale Git HEAD"):
            handoff.write(self.repo, self.packet)
        self.packet["baseline_sha"] = run_git(self.repo, "rev-parse", "HEAD")
        self.packet["branch"] = "feature/wrong-writer"
        with self.assertRaisesRegex(handoff.HandoffError, "branch mismatch"):
            handoff.write(self.repo, self.packet)
        self.assertNotEqual(old_head, self.packet["baseline_sha"])

    def test_refuses_default_branch_and_unknown_status(self):
        self.packet["branch"] = "main"
        with self.assertRaises(handoff.HandoffError):
            handoff.validate(self.packet)
        self.packet["branch"] = "feature/portable-handoff-canary"
        self.packet["status"] = "PRODUCTION_PROVEN_BY_MODEL"
        with self.assertRaises(handoff.HandoffError):
            handoff.validate(self.packet)

    def test_negative_schema_and_privacy_cases(self):
        cases = [
            ("unexpected key", lambda p: p.update(extra="unreviewed")),
            ("traversal", lambda p: p.update(canonical_path="../other/HANDOFF.md")),
            ("absolute path", lambda p: p.update(canonical_path="/tmp/other.md")),
            ("dot git", lambda p: p.update(canonical_path=".git/hooks/pre-commit.md")),
            ("hidden multiline", lambda p: p.update(mission="okay\n## injected heading")),
            ("private document", lambda p: p["accomplished"].append("docs.google.com/document/d/private")),
            ("secret field value", lambda p: p["blockers"].append("access_token=raw")),
            ("false status proof", lambda p: p.update(status="MERGED")),
            ("wrong status type", lambda p: p.update(status={"state": "MERGED"})),
            ("blocked without blocker", lambda p: p.update(status="WRITE_BLOCKED", blockers=[])),
            ("wrong check-result type", lambda p: p["checks"].append(
                {"name": "unexpected", "result": ["PASS"], "evidence": "not allowed"})),
            ("missing passing evidence", lambda p: p["checks"].append(
                {"name": "security", "result": "PASS", "evidence": ""})),
            ("untyped check", lambda p: p["checks"].append("passed")),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.packet)
                mutate(candidate)
                with self.assertRaises((handoff.HandoffError, ValueError)):
                    handoff.validate(candidate)

    def test_symlink_parent_is_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        sym = self.repo / "harness"
        try:
            sym.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("host cannot create test symlink")
        with self.assertRaisesRegex(handoff.HandoffError, "symlinked handoff parent"):
            handoff.write(self.repo, self.packet)
        self.assertFalse((outside / "handoffs/CURRENT.md").exists())

    def test_local_cli_validation_and_verify_never_claim_remote_push(self):
        packet_path = self.root / "packet.json"
        packet_path.write_text(json.dumps(self.packet), encoding="utf-8")
        cli = [__import__("sys").executable, str(ROOT / "handoff.py")]
        valid = subprocess.run(cli + ["validate", "--packet", str(packet_path)],
                               capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(valid.stdout)["result"], "VALID_PACKET_NOT_WRITTEN")
        write = subprocess.run(cli + ["write", "--packet", str(packet_path),
                                      "--repo-root", str(self.repo)],
                               capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(write.stdout)["result"], "WRITTEN_WORKTREE_NOT_COMMITTED")
        verify = subprocess.run(cli + ["verify", "--packet", str(packet_path),
                                       "--repo-root", str(self.repo)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(verify.stdout)["result"],
                         "LOCAL_CONTENT_MATCH_NOT_REMOTE_PROOF")

    def test_no_second_clone_or_hidden_provider_mutation_is_defined(self):
        script = (ROOT / "handoff.py").read_text(encoding="utf-8")
        self.assertNotIn('git(root, "clone"', script)
        self.assertNotIn('git(root, "push"', script)
        self.assertNotIn('git(root, "reset"', script)
        self.assertNotIn('git(root, "commit"', script)
        self.assertIn("WRITTEN_WORKTREE_NOT_COMMITTED", script)


if __name__ == "__main__":
    unittest.main()
