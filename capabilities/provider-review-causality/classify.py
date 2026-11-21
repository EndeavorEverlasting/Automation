#!/usr/bin/env python3
"""Provider-neutral review/run causality without mistaking quota for code defects.

This classifies explicit, bounded evidence; it does not approve PRs, retry jobs,
grant provider permissions or independently verify a review's technical claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

INPUT_SCHEMA = "automation.review-causality-input/v1"
OUTPUT_SCHEMA = "automation.review-causality-receipt/v1"
SHA = re.compile(r"^[0-9a-fA-F]{40}$")
MAX_INPUT_BYTES = 2_000_000
MAX_ATTEMPTS = 200
MAX_NOTICES = 100
MAX_FINDINGS = 1000

# The optional provider adapter imports this public exception/contract by name.
# Keep script invocation and imported-module invocation the same identity.
if __name__ == "__main__":
    sys.modules.setdefault("classify", sys.modules[__name__])
ERROR_CODES = {
    "USAGE_LIMIT_EXCEEDED": "USAGE_QUOTA",
    "QUOTA_EXHAUSTED": "USAGE_QUOTA",
    "MONTHLY_ACTIONS_QUOTA_EXHAUSTED": "USAGE_QUOTA",
    "RESOURCE_EXHAUSTED": "USAGE_QUOTA",
    "RATE_LIMITED": "RATE_LIMIT",
    "RATE_LIMIT_EXCEEDED": "RATE_LIMIT",
    "HTTP_429": "RATE_LIMIT",
    "AUTH_REQUIRED": "AUTHORIZATION",
    "UNAUTHORIZED": "AUTHORIZATION",
    "HTTP_401": "AUTHORIZATION",
    "UPSTREAM_UNAVAILABLE": "PROVIDER_UNAVAILABLE",
    "SERVICE_UNAVAILABLE": "PROVIDER_UNAVAILABLE",
    "HTTP_503": "PROVIDER_UNAVAILABLE",
}
QUOTA = re.compile(
    r"\b(?:reached (?:your |the )?(?:codex )?usage limits?|"
    r"(?:usage|monthly|code review|actions) quota (?:is |has been )?exhausted|"
    r"quota exhausted|usage_limit_exceeded|monthly_actions_quota_exhausted)\b", re.I
)
RATE = re.compile(r"\b(?:rate limits? exceeded|too many requests|rate_limit_exceeded)\b", re.I)
UNAVAILABLE = re.compile(r"\b(?:provider (?:is )?unavailable|service unavailable|upstream outage)\b", re.I)
VALID_STATUS = {"FAILED", "ERROR", "BLOCKED", "CANCELLED", "TIMED_OUT",
                "COMPLETED", "SUCCESS", "APPROVED", "PENDING",
                "QUEUED", "IN_PROGRESS", "WAITING", "UNKNOWN"}
VALID_KIND = {"CODE_REVIEW", "CI_JOB", "AGENT_RUN"}


class CausalityError(ValueError):
    pass


def _items(value: Any, name: str, maximum: int) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > maximum or not all(
        isinstance(item, dict) for item in value
    ):
        raise CausalityError(f"INVALID_{name.upper()}")
    return value


def failure_cause(attempt: dict[str, Any]) -> tuple[str, list[str]]:
    """Only machine error codes or provider-attested notices can assign cause."""
    code = attempt.get("error_code")
    if code is not None and not isinstance(code, str):
        raise CausalityError("INVALID_ERROR_CODE")
    category = ERROR_CODES.get((code or "").upper().strip())
    if category:
        return category, ["error_code"]
    notices = _items(attempt.get("notices", []), "notices", MAX_NOTICES)
    for item in notices:
        if item.get("origin") != "PROVIDER":
            continue
        text = item.get("text")
        evidence_id = item.get("id")
        if not isinstance(text, str) or len(text) > 6000 or not isinstance(evidence_id, str) or not evidence_id:
            raise CausalityError("INVALID_PROVIDER_NOTICE")
        for pattern, cause in ((QUOTA, "USAGE_QUOTA"), (RATE, "RATE_LIMIT"),
                               (UNAVAILABLE, "PROVIDER_UNAVAILABLE")):
            if pattern.search(text):
                return cause, [evidence_id[:160]]
    return "UNKNOWN", []


def classify_attempt(attempt: dict[str, Any], candidate_sha: str) -> dict[str, Any]:
    kind = str(attempt.get("kind", "")).upper()
    status = str(attempt.get("status", "UNKNOWN")).upper()
    attempt_id = attempt.get("id")
    observed_sha = attempt.get("commit_sha")
    provider = attempt.get("provider")
    if (kind not in VALID_KIND or status not in VALID_STATUS
            or not isinstance(attempt_id, str) or not 0 < len(attempt_id) <= 160
            or not isinstance(provider, str) or not 0 < len(provider) <= 100
            or not isinstance(observed_sha, str) or not SHA.fullmatch(observed_sha)):
        raise CausalityError("INVALID_ATTEMPT_IDENTITY")
    evidence_state = "CURRENT" if observed_sha.lower() == candidate_sha.lower() else "STALE"
    cause, refs = failure_cause(attempt)
    failure = status in {"FAILED", "ERROR", "BLOCKED", "CANCELLED", "TIMED_OUT"}
    complete = status in {"COMPLETED", "SUCCESS", "APPROVED"}
    waiting = status in {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING"}
    if not failure:
        cause, refs = "NONE", []
    if kind == "CI_JOB":
        steps = attempt.get("executed_steps")
        if steps is not None and (type(steps) is not int or steps < 0):
            raise CausalityError("INVALID_EXECUTED_STEPS")
        runner = attempt.get("runner_assigned")
        if runner is not None and type(runner) is not bool:
            raise CausalityError("INVALID_RUNNER_ASSIGNED")
        if failure and runner is False and steps == 0:
            execution = "NOT_STARTED"
        elif failure and steps is not None and steps > 0:
            execution = "EXECUTED_NON_SUCCESS"
        elif failure:
            execution = "NOT_COMPLETED_EXECUTION_UNKNOWN"
        elif complete and steps is not None and steps > 0:
            execution = "COMPLETED"
        elif waiting:
            execution = "WAITING"
        else:
            execution = "UNKNOWN"
    elif failure:
        execution = "NOT_COMPLETED"
    elif complete:
        execution = "COMPLETED"
    elif waiting:
        execution = "WAITING"
    else:
        execution = "UNKNOWN"

    findings = _items(attempt.get("findings", []), "findings", MAX_FINDINGS)
    finding_ids = []
    for finding in findings:
        ident = finding.get("id")
        if not isinstance(ident, str) or not 0 < len(ident) <= 160:
            raise CausalityError("INVALID_FINDING_ID")
        finding_ids.append(ident)
    if kind != "CODE_REVIEW":
        review_result = "NOT_APPLICABLE"
    elif findings and execution == "COMPLETED":
        review_result = "FINDINGS_REPORTED"
    elif findings:
        review_result = "PARTIAL_FINDINGS_REPORTED"
    elif execution == "COMPLETED" and attempt.get("no_findings_attested") is True:
        review_result = "NO_FINDINGS_REPORTED"
    elif failure:
        review_result = "NOT_ASSESSED"
    else:
        review_result = "UNDETERMINED"

    if evidence_state == "STALE":
        next_action = "REFRESH_CURRENT_SHA_EVIDENCE"
    elif review_result in {"FINDINGS_REPORTED", "PARTIAL_FINDINGS_REPORTED"}:
        next_action = "INSPECT_REPORTED_FINDINGS"
    elif cause == "USAGE_QUOTA" and failure:
        next_action = "WAIT_FOR_CAPACITY_OR_SELECT_AUTHORIZED_ALTERNATIVE"
    elif cause == "RATE_LIMIT" and failure:
        next_action = "RETRY_ONLY_AFTER_PROVIDER_BACKOFF"
    elif cause in {"AUTHORIZATION", "PROVIDER_UNAVAILABLE"} and failure:
        next_action = "RESOLVE_PROVIDER_ACCESS_OR_AVAILABILITY"
    elif failure or execution == "UNKNOWN":
        next_action = "REFRESH_PROVIDER_DIAGNOSTICS"
    elif waiting:
        next_action = "AWAIT_PROVIDER_RESULT"
    else:
        next_action = "FOLLOW_OWNER_REVIEW_POLICY"

    return {
        "id": attempt_id,
        "provider": provider,
        "kind": kind,
        "commit_sha": observed_sha,
        "candidate_alignment": evidence_state,
        "raw_provider_status": status,
        "execution_state": execution,
        "review_result": review_result,
        "failure_cause": cause,
        "cause_evidence_ids": refs,
        "reported_finding_ids": finding_ids,
        "next_action": next_action,
        "code_defect_proven": False,
    }


def classify(snapshot: dict[str, Any], *, input_source: str = "OFFLINE_NORMALIZED_INPUT") -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != INPUT_SCHEMA:
        raise CausalityError("UNSUPPORTED_INPUT_SCHEMA")
    candidate = snapshot.get("candidate")
    if not isinstance(candidate, dict) or not isinstance(candidate.get("sha"), str) or not SHA.fullmatch(candidate["sha"]):
        raise CausalityError("INVALID_CANDIDATE_SHA")
    attempts = _items(snapshot.get("attempts"), "attempts", MAX_ATTEMPTS)
    if not attempts:
        raise CausalityError("NO_REVIEW_EVIDENCE")
    sha = candidate["sha"]
    items = [classify_attempt(item, sha) for item in attempts]
    if len({item["id"] for item in items}) != len(items):
        raise CausalityError("DUPLICATE_ATTEMPT_ID")
    current = [item for item in items if item["candidate_alignment"] == "CURRENT"]
    evidence_bytes = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return {
        "schema_version": OUTPUT_SCHEMA,
        "candidate": {"sha": sha},
        "input_source": input_source,
        "attempts": items,
        "summary": {
            "current_attempt_count": len(current),
            "stale_attempt_count": len(items) - len(current),
            "provider_capacity_blocked_count": sum(item["failure_cause"] == "USAGE_QUOTA"
                                                   and item["execution_state"] in {"NOT_STARTED", "NOT_COMPLETED", "NOT_COMPLETED_EXECUTION_UNKNOWN"}
                                                   for item in current),
            "current_reported_findings_count": sum(len(item["reported_finding_ids"]) for item in current),
            "code_defect_verification": "NOT_ESTABLISHED",
        },
        "snapshot_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "proof_ceiling": "Classification of supplied evidence only; review findings do not prove defects, and provider status is not independent code or runtime validation.",
    }


def _read_snapshot(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise CausalityError("INVALID_INPUT_FILE")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CausalityError("INVALID_INPUT_JSON") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Versioned normalized evidence JSON")
    source.add_argument("--github-pr", type=int, help="Read-only GitHub PR number")
    parser.add_argument("--repo", help="Owner/repository; required with --github-pr")
    args = parser.parse_args(argv)
    try:
        if args.github_pr is not None:
            if not args.repo or args.github_pr < 1:
                raise CausalityError("INVALID_GITHUB_TARGET")
            from adapters.github_codex import github_codex_snapshot
            snapshot = github_codex_snapshot(args.repo, args.github_pr)
            source_name = "GITHUB_PROVIDER_READBACK"
        else:
            snapshot = _read_snapshot(args.input)
            source_name = "OFFLINE_NORMALIZED_INPUT"
        receipt = classify(snapshot, input_source=source_name)
    except (CausalityError, OSError) as exc:
        failure = str(exc) if isinstance(exc, CausalityError) else "LOCAL_IO_ERROR"
        print(json.dumps({"status": "BLOCKED", "failure": failure}))
        return 2
    print(json.dumps({"status": "CLASSIFIED", **receipt}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
