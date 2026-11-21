"""Read-only GitHub adapter for Codex review status and quota notices.

Only GitHub's Codex bot is a provider notice source. A bot summary's
has_any_findings flag is NOT treated as concrete review findings when the
review failed; only individually addressable inline comments are counted.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

CODEx_BOTS = frozenset({"chatgpt-codex-connector[bot]", "chatgpt-codex[bot]"})
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SUMMARY_MARKER = re.compile(r"<!--\s*codex-review-state:v1\s+(\{[^\n]*\})\s*-->")
PAGE_LIMIT = 5
PAGE_SIZE = 100
RESPONSE_BYTES = 2_000_000


def _error(code: str):
    # Local import so this adapter remains optional for offline-only consumers.
    from classify import CausalityError
    raise CausalityError(code)


def _github_json(endpoint: str) -> Any:
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=25, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        _error("GITHUB_ADAPTER_UNAVAILABLE")
    if result.returncode or len(result.stdout) > RESPONSE_BYTES:
        _error("GITHUB_PROVIDER_READ_FAILED")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        _error("GITHUB_PROVIDER_INVALID_JSON")


def _pages(endpoint: str) -> list[dict]:
    result = []
    for page in range(1, PAGE_LIMIT + 1):
        rows = _github_json(f"{endpoint}?per_page={PAGE_SIZE}&page={page}")
        if not isinstance(rows, list) or not all(isinstance(v, dict) for v in rows):
            _error("GITHUB_PROVIDER_INVALID_PAGE")
        result.extend(rows)
        if len(rows) < PAGE_SIZE:
            return result
    _error("GITHUB_PROVIDER_PAGINATION_LIMIT")


def _is_codex(item: dict) -> bool:
    user = item.get("user")
    return isinstance(user, dict) and user.get("login") in CODEx_BOTS


def _moment(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc)
    except ValueError:
        return None


def codex_snapshot(
    repo: str, pr: int, pull: dict, issue_comments: list[dict],
    inline_comments: list[dict],
) -> dict:
    """Normalize one Codex attempt pinned to its source commit, not PR summary prose."""
    from classify import INPUT_SCHEMA
    if not isinstance(pull, dict):
        _error("GITHUB_PROVIDER_INVALID_PR")
    head = (pull.get("head") or {}).get("sha")
    if not isinstance(head, str) or not re.fullmatch("[0-9a-fA-F]{40}", head):
        _error("GITHUB_PROVIDER_HEAD_MISSING")

    summaries = []
    for item in issue_comments:
        if not _is_codex(item):
            continue
        body = item.get("body")
        if not isinstance(body, str):
            continue
        marker = SUMMARY_MARKER.search(body[:12000])
        if not marker:
            continue
        try:
            data = json.loads(marker.group(1))
        except json.JSONDecodeError:
            continue
        review = data.get("code_review") if isinstance(data, dict) else None
        if not isinstance(review, dict):
            continue
        reviewed = review.get("commit_sha")
        status = review.get("status")
        if (not isinstance(reviewed, str) or not re.fullmatch("[0-9a-fA-F]{40}", reviewed)
                or not isinstance(status, str)):
            continue
        summaries.append((item, reviewed, status.upper(), review))
    if not summaries:
        _error("CODEX_REVIEW_SUMMARY_NOT_FOUND")

    matching = [s for s in summaries if s[1].lower() == head.lower()]
    ordered = sorted(matching or summaries, key=lambda s: (s[0].get("created_at") or "",
                                                             s[0].get("id") or 0))
    summary, sha, status, review = ordered[-1]
    origin = _moment(summary.get("created_at"))
    notices = []
    # Only quota notices from the SAME provider and a close time interval
    # corroborate this review attempt. Ignore user-authored issue discussions.
    if origin:
        for item in issue_comments:
            if not _is_codex(item) or item is summary:
                continue
            when = _moment(item.get("created_at"))
            body = item.get("body")
            if not when or not isinstance(body, str) or not 0 <= (when - origin).total_seconds() <= 600:
                continue
            # Time proximity alone is not attribution when the bot retried:
            # fail closed if two review attempts could own the same notice.
            candidates = [
                entry for entry in summaries
                if (started := _moment(entry[0].get("created_at"))) is not None
                and 0 <= (when - started).total_seconds() <= 600
            ]
            if len(candidates) != 1 or candidates[0][0] is not summary:
                continue
            notices.append({"origin": "PROVIDER", "id": f"github-issue-comment-{item.get('id')}",
                            "text": body[:6000]})
    findings = []
    for item in inline_comments:
        if not _is_codex(item) or str(item.get("commit_id") or "").lower() != sha.lower():
            continue
        if not isinstance(item.get("id"), int):
            continue
        findings.append({"id": f"github-inline-{item['id']}"})

    attempt = {
        "id": f"github-codex-summary-{summary.get('id')}",
        "provider": "codex",
        "kind": "CODE_REVIEW",
        "commit_sha": sha,
        "status": status,
        "notices": notices,
        "findings": findings,
        "no_findings_attested": status in {"SUCCESS", "COMPLETED", "APPROVED"} and review.get("has_any_findings") is False,
    }
    return {"schema_version": INPUT_SCHEMA, "candidate": {"sha": head},
            "attempts": [attempt]}


def github_codex_snapshot(repo: str, pr: int) -> dict:
    if not isinstance(repo, str) or not REPOSITORY.fullmatch(repo) or type(pr) is not int or pr < 1:
        _error("INVALID_GITHUB_TARGET")
    endpoint = f"repos/{repo}"
    pull = _github_json(f"{endpoint}/pulls/{pr}")
    comments = _pages(f"{endpoint}/issues/{pr}/comments")
    inline = _pages(f"{endpoint}/pulls/{pr}/comments")
    # Provider readback must pin one immutable head across all page requests.
    after = _github_json(f"{endpoint}/pulls/{pr}")
    before_sha = (pull.get("head") or {}).get("sha") if isinstance(pull, dict) else None
    after_sha = (after.get("head") or {}).get("sha") if isinstance(after, dict) else None
    if not isinstance(before_sha, str) or before_sha != after_sha:
        _error("GITHUB_PR_HEAD_MOVED")
    return codex_snapshot(repo, pr, after, comments, inline)
