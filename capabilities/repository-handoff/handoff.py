#!/usr/bin/env python3
"""Validate, render, and safely write a canonical handoff in an existing Git repo.

No clones, provider writes, git add/commit/push, deployments or archive exports.
Only a trusted executor supplies packets; their text is never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

VERSION = "automation-repository-handoff/v1"
STATES = frozenset(("CANDIDATE", "COMMITTED", "PUSHED", "PR_OPEN", "MERGED",
                    "DEPLOYED", "LIVE_OBSERVED", "WRITE_BLOCKED", "VALIDATION_BLOCKED"))
RESULTS = frozenset(("PASS", "FAIL", "BLOCKED", "NOT_RUN"))
REQUIRED = frozenset(("schema_version", "work_id", "repository_id", "branch",
                      "baseline_sha", "canonical_path", "mission", "status",
                      "owned_scope", "forbidden_scope", "accomplished", "checks",
                      "blockers", "evidence_refs", "next_action", "proof_ceiling"))
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,159}\Z")
PRIVATE = re.compile(
    r"(?i)(?:drive\.google\.com|docs\.google\.com|"
    r"https?://[^/\s]*@|"
    r"[a-z]:[/\\]users[/\\][^/\\]+|/users/[^/]+/|/home/[^/]+/|"
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|cookie)\s*[:=])"
)


class HandoffError(ValueError):
    """A deterministic refusal; never turn it into an implicit fallback export."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HandoffError(message)


def text_field(value, name: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), name + " must be nonempty text")
    require(len(value) <= 500, name + " exceeds 500 characters")
    require(not any(c in value for c in ("\n", "\r", "\0", "<", ">")),
            name + " must be a single plain-text line")
    require(not PRIVATE.search(value), name + " contains a private locator or secret-like value")
    return value


def repo_relative(value, name: str, *, markdown=False) -> str:
    text_field(value, name)
    require("\\" not in value and not value.startswith("/"), name + " must be POSIX relative")
    path = PurePosixPath(value)
    parts = value.split("/")
    require(all(p not in ("", ".", "..") for p in parts), name + " has unsafe path segments")
    require(not any(p.lower() == ".git" for p in parts), name + " targets Git internals")
    require(len(parts) >= 2, name + " needs a directory and a file")
    if markdown:
        require(path.suffix == ".md", name + " must be a markdown handoff")
    return value


def array_field(value, name: str, *, nonempty=False):
    require(isinstance(value, list), name + " must be a list")
    if nonempty:
        require(bool(value), name + " must not be empty")
    require(len(value) <= 100, name + " exceeds maximum entries")
    for i, item in enumerate(value):
        text_field(item, f"{name}[{i}]")
    return value


def validate(payload):
    require(isinstance(payload, dict), "packet must be a JSON object")
    require(set(payload) == REQUIRED,
            "packet keys must match the canonical handoff contract")
    require(payload["schema_version"] == VERSION, "unsupported handoff schema")
    require(bool(IDENTIFIER.fullmatch(text_field(payload["work_id"], "work_id"))),
            "unsafe work_id")
    require(bool(IDENTIFIER.fullmatch(text_field(payload["repository_id"], "repository_id"))),
            "unsafe repository_id")
    branch = text_field(payload["branch"], "branch")
    require(branch not in ("main", "master") and not branch.startswith("-"),
            "handoff writes must target a task branch, not the default branch")
    require(bool(SHA40.fullmatch(text_field(payload["baseline_sha"], "baseline_sha"))),
            "baseline_sha must be the exact 40-character Git commit")
    repo_relative(payload["canonical_path"], "canonical_path", markdown=True)
    for name in ("mission", "next_action", "proof_ceiling"):
        text_field(payload[name], name)
    require(payload["status"] in STATES, "unknown handoff status")
    for name in ("owned_scope", "forbidden_scope"):
        array_field(payload[name], name, nonempty=True)
    for name in ("accomplished", "blockers", "evidence_refs"):
        array_field(payload[name], name)
    checks = payload["checks"]
    require(isinstance(checks, list) and len(checks) <= 100, "checks must be a list")
    for i, check in enumerate(checks):
        require(isinstance(check, dict) and set(check) == {"name", "result", "evidence"},
                f"checks[{i}] must have exact name/result/evidence")
        text_field(check["name"], f"checks[{i}].name")
        require(check["result"] in RESULTS, f"checks[{i}] invalid result")
        if check["result"] in ("PASS", "FAIL"):
            text_field(check["evidence"], f"checks[{i}].evidence")
        else:
            require(isinstance(check["evidence"], str), "evidence must be a string")
            if check["evidence"]:
                text_field(check["evidence"], f"checks[{i}].evidence")
    if payload["status"] in ("COMMITTED", "PUSHED", "PR_OPEN", "MERGED",
                             "DEPLOYED", "LIVE_OBSERVED"):
        require(bool(payload["evidence_refs"]), "proof-bearing status needs evidence_refs")
    # No freeform raw content. Output always comes from validated fields.
    return payload


def quote(value: str) -> str:
    """Escape Markdown format controls, without supporting arbitrary markup."""
    return re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", value)


def render(payload) -> str:
    p = validate(payload)
    def bullets(values):
        return "\n".join(f"- {quote(x)}" for x in values) if values else "- None recorded"
    checks = "\n".join(
        f"- {quote(x['name'])}: **{x['result']}**"
        + (f" — {quote(x['evidence'])}" if x["evidence"] else "")
        for x in p["checks"]
    ) or "- No checks recorded"
    return (
        "# Canonical repository handoff\n\n"
        f"Work ID: `{quote(p['work_id'])}`  \n"
        f"Repository: `{quote(p['repository_id'])}`  \n"
        f"Task branch: `{quote(p['branch'])}`  \n"
        f"Baseline SHA: `{p['baseline_sha']}`  \n"
        f"Status: **{p['status']}**\n\n"
        f"## Mission\n\n{quote(p['mission'])}\n\n"
        f"## Owned scope\n\n{bullets(p['owned_scope'])}\n\n"
        f"## Forbidden scope\n\n{bullets(p['forbidden_scope'])}\n\n"
        f"## Completed work (as reported)\n\n{bullets(p['accomplished'])}\n\n"
        f"## Checks and evidence\n\n{checks}\n\n"
        f"## Blockers\n\n{bullets(p['blockers'])}\n\n"
        f"## Evidence references\n\n{bullets(p['evidence_refs'])}\n\n"
        f"## Exact next action\n\n{quote(p['next_action'])}\n\n"
        f"## Proof ceiling\n\n{quote(p['proof_ceiling'])}\n\n"
        "This file is a repository-owned continuity artifact, not a substitute for "
        "provider commit/PR readback or runtime verification. Do not ask the operator "
        "to download or extract a patch archive.\n"
    )


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise HandoffError("Git context unavailable: " + " ".join(args))
    return result.stdout.strip()


def owned_destination(repo_root: Path, payload) -> tuple[Path, str]:
    p = validate(payload)
    require(repo_root.is_dir() and not repo_root.is_symlink(), "repo root missing/symlink")
    root = repo_root.resolve(strict=True)
    top = Path(git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    require(top == root, "repo-root must identify the existing canonical checkout root")
    branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    require(branch == p["branch"], "branch mismatch; do not write to another agent's branch")
    head = git(root, "rev-parse", "HEAD")
    require(head == p["baseline_sha"], "stale Git HEAD; refresh the packet before writing")
    current = root
    for name in p["canonical_path"].split("/")[:-1]:
        current = current / name
        require(not current.is_symlink(), "symlinked handoff parent is forbidden")
    target = root / p["canonical_path"]
    require(not target.is_symlink(), "symlinked handoff file is forbidden")
    require(not target.exists() or target.is_file(), "handoff target is not a regular file")
    return target, head


def write(repo_root: Path, payload, *, expected_sha256=None):
    target, head = owned_destination(repo_root, payload)
    rendered = render(payload).encode("utf-8")
    if target.exists():
        require(isinstance(expected_sha256, str) and SHA256.fullmatch(expected_sha256),
                "existing handoff requires explicit 64-character expected_sha256")
        old = hashlib.sha256(target.read_bytes()).hexdigest()
        require(old == expected_sha256, "handoff preimage changed; preserve existing work")
    else:
        require(expected_sha256 is None, "new handoff must not specify existing-file digest")
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=str(target.parent),
                                         prefix=".handoff-", delete=False) as tmp:
            handle = Path(tmp.name)
            tmp.write(rendered)
            tmp.flush()
            os.fsync(tmp.fileno())
        # Check again immediately before replace; no destructive cleanup on failure.
        if expected_sha256 is not None:
            require(hashlib.sha256(target.read_bytes()).hexdigest() == expected_sha256,
                    "handoff concurrently changed; refusal")
        else:
            require(not target.exists(), "handoff appeared concurrently; refusal")
        os.replace(handle, target)
        handle = None
    finally:
        if handle and handle.exists():
            handle.unlink()
    return {"result": "WRITTEN_WORKTREE_NOT_COMMITTED",
            "path": payload["canonical_path"],
            "sha256": hashlib.sha256(rendered).hexdigest(),
            "git_head_sha": head, "git_branch": payload["branch"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "render", "write", "verify"))
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args(argv)
    try:
        p = validate(json.loads(args.packet.read_text(encoding="utf-8")))
        if args.action == "validate":
            result = {"result": "VALID_PACKET_NOT_WRITTEN", "work_id": p["work_id"]}
        elif args.action == "render":
            sys.stdout.write(render(p))
            return 0
        else:
            require(args.repo_root is not None, "write/verify require --repo-root")
            if args.action == "write":
                result = write(args.repo_root, p, expected_sha256=args.expected_sha256)
            else:
                target, head = owned_destination(args.repo_root, p)
                require(target.is_file(), "canonical handoff is missing")
                require(target.read_bytes() == render(p).encode("utf-8"),
                        "canonical handoff differs from packet")
                result = {"result": "LOCAL_CONTENT_MATCH_NOT_REMOTE_PROOF",
                          "path": p["canonical_path"], "git_head_sha": head}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (HandoffError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "REFUSED", "reason": str(exc)}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
