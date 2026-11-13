"""Offline causality regression suite. Uses synthetic provider events, no accounts."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "capabilities" / "provider-review-causality"
sys.path.insert(0, str(CAP))
import classify as C
from adapters import github_codex as G

SHA = "a" * 40
OLD = "b" * 40


def attempt(**changes):
    item = {
        "id": "run-1", "provider": "codex", "kind": "CODE_REVIEW",
        "commit_sha": SHA, "status": "FAILED", "notices": [],
        "findings": [],
    }
    item.update(changes)
    return item


def snapshot(*items):
    return {"schema_version": C.INPUT_SCHEMA, "candidate": {"sha": SHA},
            "attempts": list(items or (attempt(),))}


class ProviderCausalityTests(unittest.TestCase):
    def test_quota_failed_review_is_not_failed_code(self):
        data = snapshot(attempt(
            notices=[{"id": "github-issue-comment-1002", "origin": "PROVIDER",
                      "text": "You have reached your Codex usage limits for code reviews."}]))
        result = C.classify(data)
        review = result["attempts"][0]
        self.assertEqual(review["failure_cause"], "USAGE_QUOTA")
        self.assertEqual(review["execution_state"], "NOT_COMPLETED")
        self.assertEqual(review["review_result"], "NOT_ASSESSED")
        self.assertFalse(review["code_defect_proven"])
        self.assertEqual(review["cause_evidence_ids"], ["github-issue-comment-1002"])
        self.assertEqual(result["summary"]["current_reported_findings_count"], 0)
        self.assertEqual(result["summary"]["provider_capacity_blocked_count"], 1)
        self.assertEqual(result["summary"]["code_defect_verification"], "NOT_ESTABLISHED")
        self.assertEqual(review["next_action"], "WAIT_FOR_CAPACITY_OR_SELECT_AUTHORIZED_ALTERNATIVE")
        self.assertNotIn("You have reached", json.dumps(result))

    def test_failed_unknown_review_never_implies_defects_or_quota(self):
        result = C.classify(snapshot(attempt()))
        r = result["attempts"][0]
        self.assertEqual(r["failure_cause"], "UNKNOWN")
        self.assertEqual(r["review_result"], "NOT_ASSESSED")
        self.assertEqual(r["next_action"], "REFRESH_PROVIDER_DIAGNOSTICS")

    def test_user_discussion_is_not_attested_provider_error(self):
        data = snapshot(attempt(
            notices=[{"id": "discussion-1", "origin": "DISCUSSION",
                      "text": "I heard Codex usage limits were reached."}]))
        self.assertEqual(C.classify(data)["attempts"][0]["failure_cause"], "UNKNOWN")

    def test_machine_code_takes_priority_over_untrusted_message(self):
        data = snapshot(attempt(error_code="usage_limit_exceeded",
                                notices=[{"id": "discussion", "origin": "DISCUSSION",
                                          "text": "This is a syntax bug."}]))
        item = C.classify(data)["attempts"][0]
        self.assertEqual(item["failure_cause"], "USAGE_QUOTA")
        self.assertEqual(item["cause_evidence_ids"], ["error_code"])

    def test_findings_are_separate_from_failed_capacity_review(self):
        result = C.classify(snapshot(
            attempt(id="quota", notices=[{"id": "notice", "origin": "PROVIDER",
                    "text": "Usage quota exhausted."}]),
            attempt(id="actual-findings", provider="codeant", status="COMPLETED",
                    findings=[{"id": "review-comment-88"}])))
        self.assertEqual(result["summary"]["current_reported_findings_count"], 1)
        self.assertEqual(result["attempts"][0]["review_result"], "NOT_ASSESSED")
        self.assertEqual(result["attempts"][1]["review_result"], "FINDINGS_REPORTED")
        self.assertFalse(result["attempts"][1]["code_defect_proven"])

    def test_partial_findings_are_retained_without_full_review_claim(self):
        r = C.classify(snapshot(attempt(findings=[{"id": "partial-1"}],
                                         error_code="QUOTA_EXHAUSTED")))["attempts"][0]
        self.assertEqual(r["review_result"], "PARTIAL_FINDINGS_REPORTED")
        self.assertEqual(r["next_action"], "INSPECT_REPORTED_FINDINGS")

    def test_no_findings_requires_explicit_attestation_and_completed_run(self):
        only_success = C.classify(snapshot(attempt(status="SUCCESS")))["attempts"][0]
        self.assertEqual(only_success["review_result"], "UNDETERMINED")
        explicit = C.classify(snapshot(attempt(status="SUCCESS", no_findings_attested=True)))["attempts"][0]
        self.assertEqual(explicit["review_result"], "NO_FINDINGS_REPORTED")
        failed = C.classify(snapshot(attempt(status="FAILED", no_findings_attested=True)))["attempts"][0]
        self.assertEqual(failed["review_result"], "NOT_ASSESSED")

    def test_stale_review_is_never_current_provider_truth(self):
        r = C.classify(snapshot(attempt(commit_sha=OLD, error_code="USAGE_LIMIT_EXCEEDED")))
        self.assertEqual(r["attempts"][0]["candidate_alignment"], "STALE")
        self.assertEqual(r["attempts"][0]["next_action"], "REFRESH_CURRENT_SHA_EVIDENCE")
        self.assertEqual(r["summary"]["provider_capacity_blocked_count"], 0)
        self.assertEqual(r["summary"]["stale_attempt_count"], 1)

    def test_ci_runner_admission_distinct_from_executed_failed_test(self):
        before = C.classify(snapshot(attempt(kind="CI_JOB", provider="github",
            executed_steps=0, runner_assigned=False, error_code="MONTHLY_ACTIONS_QUOTA_EXHAUSTED")))["attempts"][0]
        self.assertEqual(before["execution_state"], "NOT_STARTED")
        self.assertEqual(before["failure_cause"], "USAGE_QUOTA")
        after = C.classify(snapshot(attempt(kind="CI_JOB", provider="github",
            executed_steps=4, runner_assigned=True)))["attempts"][0]
        self.assertEqual(after["execution_state"], "EXECUTED_NON_SUCCESS")
        self.assertEqual(after["failure_cause"], "UNKNOWN")
        self.assertEqual(after["review_result"], "NOT_APPLICABLE")

    def test_rate_limit_and_auth_are_not_code_findings(self):
        for code, expected in (("HTTP_429", "RATE_LIMIT"), ("HTTP_401", "AUTHORIZATION"),
                               ("HTTP_503", "PROVIDER_UNAVAILABLE")):
            with self.subTest(code=code):
                self.assertEqual(C.classify(snapshot(attempt(error_code=code)))["attempts"][0]["failure_cause"], expected)

    def test_invalid_and_duplicate_evidence_fail_closed(self):
        with self.assertRaises(C.CausalityError):
            C.classify(snapshot(attempt(id="same"), attempt(id="same")))
        with self.assertRaises(C.CausalityError):
            C.classify({"schema_version": C.INPUT_SCHEMA, "candidate": {"sha": SHA}, "attempts": []})
        with self.assertRaises(C.CausalityError):
            C.classify(snapshot(attempt(findings=["not-a-finding"])))
        with self.assertRaises(C.CausalityError):
            C.classify(snapshot(attempt(notices=[{"origin": "PROVIDER", "text": "quota exhausted"}])))

    def test_cli_synthetic_causality_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            path.write_text(json.dumps(snapshot(attempt(error_code="usage_limit_exceeded"))),
                            encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CAP / "classify.py"), "--input", str(path)],
                capture_output=True, text=True, timeout=12, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(result.stdout)
            self.assertEqual(packet["schema_version"], C.OUTPUT_SCHEMA)
            self.assertEqual(packet["status"], "CLASSIFIED")
            self.assertEqual(packet["input_source"], "OFFLINE_NORMALIZED_INPUT")

    def test_github_codex_bot_provider_notice_bound_to_same_attempt(self):
        start = "2026-11-13T16:26:46Z"
        review = {"code_review": {"commit_sha": SHA, "status": "failed",
                                  "has_any_findings": True, "has_unresolved_findings": True}}
        summary = {"id": 1001, "user": {"login": "chatgpt-codex-connector[bot]"},
                   "created_at": start, "body":
                   "<!-- codex-review-state:v1 " + json.dumps(review) + " -->"}
        provider_notice = {"id": 1002, "user": {"login": "chatgpt-codex-connector[bot]"},
                           "created_at": "2026-11-13T16:26:48Z",
                           "body": "You have reached your Codex usage limits for code reviews."}
        user_quote = {"id": 1003, "user": {"login": "developer"},
                      "created_at": "2026-11-13T16:26:50Z",
                      "body": "Usage limits for code reviews."}
        other_review_finding = {"id": 1004, "user": {"login": "codeant-ai[bot]"},
                                "commit_id": SHA}
        normalized = G.codex_snapshot("org/repo", 50, {"head": {"sha": SHA}},
                                      [summary, provider_notice, user_quote], [other_review_finding])
        self.assertEqual(normalized["attempts"][0]["findings"], [])
        self.assertEqual(len(normalized["attempts"][0]["notices"]), 1)
        result = C.classify(normalized, input_source="GITHUB_PROVIDER_READBACK")
        item = result["attempts"][0]
        self.assertEqual(item["review_result"], "NOT_ASSESSED")
        self.assertEqual(item["failure_cause"], "USAGE_QUOTA")
        self.assertEqual(item["candidate_alignment"], "CURRENT")
        self.assertEqual(item["cause_evidence_ids"], ["github-issue-comment-1002"])
        self.assertEqual(result["input_source"], "GITHUB_PROVIDER_READBACK")

    def test_github_adapter_protects_current_commit_and_provider_identity(self):
        summary = {"id": 10, "user": {"login": "chatgpt-codex-connector[bot]"},
                   "created_at": "2026-11-13T12:00:00Z",
                   "body": "<!-- codex-review-state:v1 " +
                   json.dumps({"code_review": {"commit_sha": OLD, "status": "failed"}}) + " -->"}
        quota = {"id": 11, "user": {"login": "other-bot"},
                 "created_at": "2026-11-13T12:00:01Z",
                 "body": "You have reached your Codex usage limits for code reviews."}
        payload = G.codex_snapshot("org/repo", 50, {"head": {"sha": SHA}},
                                   [summary, quota], [])
        item = C.classify(payload)["attempts"][0]
        self.assertEqual(item["candidate_alignment"], "STALE")
        self.assertEqual(item["failure_cause"], "UNKNOWN")

    def test_github_adapter_read_is_bounded_and_no_shell(self):
        with mock.patch.object(G.subprocess, "run", return_value=mock.Mock(
            returncode=0, stdout='{"head":{"sha":"' + SHA + '"}}', stderr="")) as runner:
            value = G._github_json("repos/org/repo/pulls/4")
            self.assertEqual(value["head"]["sha"], SHA)
            self.assertEqual(runner.call_args.args[0], ["gh", "api", "repos/org/repo/pulls/4"])
            self.assertNotIn("shell", runner.call_args.kwargs)

    def test_missing_github_provider_session_returns_typed_error(self):
        with mock.patch.object(G.subprocess, "run", side_effect=FileNotFoundError("gh")):
            with self.assertRaises(C.CausalityError) as exc:
                G.github_codex_snapshot("org/repo", 50)
        self.assertEqual(str(exc.exception), "GITHUB_ADAPTER_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
