from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

GATE_ORDER = [
    "REPOSITORY_CHECKOUT_CURRENT",
    "AGENT_PROJECTION_MATCHES_BASELINE",
    "LOCAL_AGENT_RUNTIME_VERIFIED",
    "REMOTE_WRITE_VERIFIED",
    "ACTUAL_PUSH_PROVEN",
]


class ReadinessError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], root)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReadinessError(f"{path} must contain a JSON object")
    return value


def _path_is_safe(path: str) -> bool:
    if not path or chr(92) in path:
        return False
    candidate = Path(path)
    if candidate.is_absolute():
        return False
    return all(part not in {"", ".", ".."} for part in candidate.parts)


def normalize_remote_identity(remote_url: str | None) -> str | None:
    if not remote_url:
        return None
    value = remote_url.strip().rstrip("/")
    scp = re.match(r"^[^@\s]+@([^:]+):(.+)$", value)
    if scp:
        host = scp.group(1).lower()
        path = re.sub(r"\.git$", "", scp.group(2).strip("/"), flags=re.IGNORECASE)
        return f"{host}/{path}" if path else None
    parsed = urlparse(value)
    if parsed.scheme and parsed.hostname:
        path = re.sub(r"\.git$", "", parsed.path.strip("/"), flags=re.IGNORECASE)
        return f"{parsed.hostname.lower()}/{path}" if path else parsed.hostname.lower()
    return None


def load_profile(path: Path) -> dict[str, Any]:
    profile = _load_json(path)
    if profile.get("schema_version") != "local-agent-readiness-profile/v1":
        raise ReadinessError("unsupported local-agent-readiness profile schema")

    repository = profile.get("repository")
    projection_sets = profile.get("projection_sets")
    agents = profile.get("agents")
    remote_write = profile.get("remote_write")

    if not isinstance(repository, dict):
        raise ReadinessError("profile.repository must be an object")
    if not isinstance(projection_sets, list) or not projection_sets:
        raise ReadinessError("profile.projection_sets must be a non-empty array")
    if not isinstance(agents, list) or not agents:
        raise ReadinessError("profile.agents must be a non-empty array")
    if not isinstance(remote_write, dict):
        raise ReadinessError("profile.remote_write must be an object")

    for key in ("remote", "baseline_branch"):
        if not isinstance(repository.get(key), str) or not repository[key].strip():
            raise ReadinessError(f"profile.repository.{key} must be non-empty")
    remote_identity = repository.get("remote_identity")
    if remote_identity is not None and (
        not isinstance(remote_identity, str) or not remote_identity.strip()
    ):
        raise ReadinessError("profile.repository.remote_identity must be null or non-empty")

    set_ids: set[str] = set()
    for item in projection_sets:
        if not isinstance(item, dict):
            raise ReadinessError("projection set must be an object")
        set_id = item.get("id")
        paths = item.get("paths")
        if not isinstance(set_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", set_id):
            raise ReadinessError(f"invalid projection set id: {set_id!r}")
        if set_id in set_ids:
            raise ReadinessError(f"duplicate projection set id: {set_id}")
        set_ids.add(set_id)
        if not isinstance(paths, list) or not paths or not all(
            isinstance(path, str) and _path_is_safe(path) for path in paths
        ):
            raise ReadinessError(
                f"projection set {set_id} paths must be safe repository-relative paths"
            )
        if len(paths) != len(set(paths)):
            raise ReadinessError(f"projection set {set_id} contains duplicate paths")

    agent_ids: set[str] = set()
    for agent in agents:
        if not isinstance(agent, dict):
            raise ReadinessError("agent profile must be an object")
        agent_id = agent.get("agent_id")
        if not isinstance(agent_id, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9._-]*", agent_id
        ):
            raise ReadinessError(f"invalid agent id: {agent_id!r}")
        if agent_id in agent_ids:
            raise ReadinessError(f"duplicate agent id: {agent_id}")
        agent_ids.add(agent_id)

        refs = agent.get("projection_sets")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(ref, str) and ref in set_ids for ref in refs
        ):
            raise ReadinessError(
                f"agent {agent_id} must reference known projection sets"
            )
        if len(refs) != len(set(refs)):
            raise ReadinessError(f"agent {agent_id} has duplicate projection sets")

        required_gates = agent.get("required_gates")
        if not isinstance(required_gates, list) or not required_gates:
            raise ReadinessError(f"agent {agent_id} required_gates must be non-empty")
        unknown_gates = sorted(set(required_gates) - set(GATE_ORDER))
        if unknown_gates:
            raise ReadinessError(
                f"agent {agent_id} has unsupported readiness gates: {unknown_gates}"
            )
        if len(required_gates) != len(set(required_gates)):
            raise ReadinessError(f"agent {agent_id} has duplicate required gates")

        claims = agent.get("runtime_claims_required")
        if not isinstance(claims, list) or not all(
            isinstance(claim, str) and claim.strip() for claim in claims
        ):
            raise ReadinessError(
                f"agent {agent_id} runtime_claims_required must be an array of strings"
            )
        if len(claims) != len(set(claims)):
            raise ReadinessError(f"agent {agent_id} has duplicate runtime claims")

    namespace = remote_write.get("dry_run_namespace")
    if not isinstance(namespace, str) or not namespace.startswith("refs/heads/"):
        raise ReadinessError(
            "profile.remote_write.dry_run_namespace must be an explicit refs/heads/* namespace"
        )
    return profile


def _agent(profile: dict[str, Any], agent_id: str) -> dict[str, Any]:
    for agent in profile["agents"]:
        if agent["agent_id"] == agent_id:
            return agent
    raise ReadinessError(f"agent {agent_id!r} is not defined by the profile")


def _projection_sets_by_id(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in profile["projection_sets"]}


def projection_paths(profile: dict[str, Any], agent_id: str) -> list[str]:
    agent = _agent(profile, agent_id)
    sets = _projection_sets_by_id(profile)
    paths: list[str] = []
    for set_id in agent["projection_sets"]:
        paths.extend(sets[set_id]["paths"])
    return sorted(set(paths))


def agent_profile_digest(profile: dict[str, Any], agent_id: str) -> str:
    agent = _agent(profile, agent_id)
    sets = _projection_sets_by_id(profile)
    referenced = [sets[set_id] for set_id in agent["projection_sets"]]
    payload = {
        "schema_version": profile["schema_version"],
        "repository": profile["repository"],
        "agent": agent,
        "projection_sets": sorted(referenced, key=lambda item: item["id"]),
        "remote_write": profile["remote_write"],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve(root: Path, ref: str) -> str | None:
    proc = _git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


def _gate(state: str, reason: str, **evidence: Any) -> dict[str, Any]:
    return {"state": state, "reason": reason, "evidence": evidence}


def _changed(root: Path, args: list[str]) -> tuple[bool, list[str]]:
    proc = _git(root, *args)
    if proc.returncode != 0:
        return False, []
    return True, sorted(line.strip() for line in proc.stdout.splitlines() if line.strip())


def _projection_changes(
    root: Path,
    *,
    base: str,
    head: str,
    paths: list[str],
) -> tuple[bool, dict[str, list[str]]]:
    ok_committed, committed = _changed(
        root, ["diff", "--name-only", f"{base}..{head}", "--", *paths]
    )
    ok_staged, staged = _changed(
        root, ["diff", "--cached", "--name-only", "--", *paths]
    )
    ok_unstaged, unstaged = _changed(
        root, ["diff", "--name-only", "--", *paths]
    )
    ok_untracked, untracked = _changed(
        root, ["ls-files", "--others", "--exclude-standard", "--", *paths]
    )
    return (
        all((ok_committed, ok_staged, ok_unstaged, ok_untracked)),
        {
            "committed": committed,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
        },
    )


def _baseline_files(root: Path, baseline: str, paths: list[str]) -> tuple[bool, list[str]]:
    proc = _git(root, "ls-tree", "-r", "--name-only", baseline, "--", *paths)
    if proc.returncode != 0:
        return False, []
    return True, sorted(line.strip() for line in proc.stdout.splitlines() if line.strip())


def _checkout_gate(
    root: Path,
    *,
    profile: dict[str, Any],
    refresh_remote: bool,
) -> tuple[dict[str, Any], str | None, str | None, dict[str, Any]]:
    repository = profile["repository"]
    remote = repository["remote"]
    branch = repository["baseline_branch"]
    remote_ref = f"refs/remotes/{remote}/{branch}"
    local_head = _resolve(root, "HEAD")
    refresh = {"attempted": refresh_remote, "state": "NOT_RUN", "return_code": None}

    url_proc = _git(root, "remote", "get-url", remote)
    if url_proc.returncode != 0:
        return (
            _gate(
                "BLOCKED",
                "Configured remote URL is unavailable.",
                remote=remote,
            ),
            None,
            local_head,
            refresh,
        )
    observed_identity = normalize_remote_identity(url_proc.stdout.strip())
    expected_identity = repository.get("remote_identity")
    if expected_identity and observed_identity != expected_identity:
        return (
            _gate(
                "FAIL",
                "Configured remote identity does not match the readiness profile.",
                remote=remote,
                expected_remote_identity=expected_identity,
                observed_remote_identity=observed_identity,
            ),
            None,
            local_head,
            refresh,
        )

    if not refresh_remote:
        return (
            _gate(
                "BLOCKED",
                "Remote baseline was not refreshed in this run.",
                remote=remote,
                baseline_branch=branch,
                observed_remote_identity=observed_identity,
            ),
            _resolve(root, remote_ref),
            local_head,
            refresh,
        )

    fetch = _git(
        root,
        "fetch",
        remote,
        f"+refs/heads/{branch}:{remote_ref}",
    )
    refresh["return_code"] = fetch.returncode
    refresh["state"] = "PASS" if fetch.returncode == 0 else "FAIL"
    if fetch.returncode != 0:
        return (
            _gate(
                "BLOCKED",
                "Remote baseline refresh failed.",
                remote=remote,
                baseline_branch=branch,
                observed_remote_identity=observed_identity,
            ),
            None,
            local_head,
            refresh,
        )

    baseline = _resolve(root, remote_ref)
    local_head = _resolve(root, "HEAD")
    if not baseline or not local_head:
        return (
            _gate(
                "BLOCKED",
                "Unable to resolve refreshed baseline or local HEAD.",
                remote_ref=remote_ref,
                remote_baseline_sha=baseline,
                local_head=local_head,
            ),
            baseline,
            local_head,
            refresh,
        )

    ancestry = _git(root, "merge-base", "--is-ancestor", baseline, local_head)
    if ancestry.returncode == 0:
        return (
            _gate(
                "PASS",
                "Local HEAD contains the refreshed remote baseline.",
                remote_ref=remote_ref,
                remote_baseline_sha=baseline,
                local_head=local_head,
                observed_remote_identity=observed_identity,
            ),
            baseline,
            local_head,
            refresh,
        )
    return (
        _gate(
            "FAIL",
            "Local HEAD does not contain the refreshed remote baseline.",
            remote_ref=remote_ref,
            remote_baseline_sha=baseline,
            local_head=local_head,
            observed_remote_identity=observed_identity,
        ),
        baseline,
        local_head,
        refresh,
    )


def _projection_gate(
    root: Path,
    *,
    baseline: str | None,
    local_head: str | None,
    paths: list[str],
) -> dict[str, Any]:
    if not baseline or not local_head:
        return _gate(
            "BLOCKED",
            "Projection parity requires a resolvable refreshed baseline and local HEAD.",
        )

    baseline_ok, baseline_files = _baseline_files(root, baseline, paths)
    if not baseline_ok:
        return _gate("BLOCKED", "Unable to enumerate baseline projection files.")
    if not baseline_files:
        return _gate(
            "FAIL",
            "Declared projection paths do not resolve to tracked files on the baseline.",
            projection_paths=paths,
        )

    missing = [name for name in baseline_files if not (root / name).is_file()]
    changes_ok, changes = _projection_changes(
        root, base=baseline, head=local_head, paths=paths
    )
    if not changes_ok:
        return _gate(
            "BLOCKED",
            "Unable to compare local projection surfaces against the baseline.",
            projection_paths=paths,
        )

    changed_paths = sorted(
        set(
            changes["committed"]
            + changes["staged"]
            + changes["unstaged"]
            + changes["untracked"]
            + missing
        )
    )
    if changed_paths:
        return _gate(
            "FAIL",
            "Local agent projection differs from the refreshed baseline.",
            projection_paths=paths,
            changed_paths=changed_paths,
            changes=changes,
            missing_tracked_files=missing,
        )

    return _gate(
        "PASS",
        "Local agent projection matches the refreshed baseline.",
        projection_paths=paths,
        tracked_file_count=len(baseline_files),
        remote_baseline_sha=baseline,
        local_head=local_head,
    )


def _load_runtime_observation(path: Path) -> dict[str, Any]:
    observation = _load_json(path)
    required = {
        "schema_version",
        "agent_id",
        "status",
        "proof_class",
        "observed_at",
        "floor_sha",
        "agent_profile_sha256",
        "claims",
        "raw_private_content_persisted",
        "proof_ceiling",
    }
    missing = sorted(required - set(observation))
    if missing:
        raise ReadinessError(
            "runtime observation missing required fields: " + ", ".join(missing)
        )
    if observation["schema_version"] != "local-agent-runtime-observation/v1":
        raise ReadinessError("unsupported runtime observation schema")
    if observation["proof_class"] != "LIVE_HOST_OBSERVATION":
        raise ReadinessError("runtime observation proof_class must be LIVE_HOST_OBSERVATION")
    if observation["raw_private_content_persisted"] is not False:
        raise ReadinessError("runtime observation must not persist raw private content")
    if not isinstance(observation["claims"], list):
        raise ReadinessError("runtime observation claims must be an array")
    return observation


def _runtime_gate(
    root: Path,
    *,
    agent_id: str,
    agent: dict[str, Any],
    profile_digest: str,
    observation_path: Path | None,
    local_head: str | None,
    paths: list[str],
) -> dict[str, Any]:
    if observation_path is None:
        return _gate("NOT_RUN", "No normalized live-host observation was supplied.")
    path = observation_path.expanduser().resolve()
    if not path.is_file():
        return _gate(
            "FAIL",
            "Normalized live-host observation does not exist.",
            observation=str(path),
        )
    try:
        observation = _load_runtime_observation(path)
    except ReadinessError as exc:
        return _gate(
            "FAIL",
            "Normalized live-host observation is invalid.",
            observation=str(path),
            error=str(exc),
        )

    if observation["agent_id"] != agent_id:
        return _gate(
            "FAIL",
            "Live-host observation belongs to a different agent profile.",
            expected_agent_id=agent_id,
            observed_agent_id=observation["agent_id"],
        )
    if observation["status"] != "PASS":
        return _gate(
            "FAIL",
            "Live-host observation status is not PASS.",
            observed_status=observation["status"],
        )
    if observation["agent_profile_sha256"] != profile_digest:
        return _gate(
            "FAIL",
            "Live-host observation was produced for a different agent profile revision.",
            expected_agent_profile_sha256=profile_digest,
            observed_agent_profile_sha256=observation["agent_profile_sha256"],
        )

    claim_states: dict[str, str] = {}
    for claim in observation["claims"]:
        if not isinstance(claim, dict):
            return _gate("FAIL", "Live-host observation contains a malformed claim.")
        claim_id = claim.get("id")
        state = claim.get("state")
        if not isinstance(claim_id, str) or not isinstance(state, str):
            return _gate("FAIL", "Live-host observation contains a malformed claim.")
        claim_states[claim_id] = state

    missing_claims = [
        claim
        for claim in agent["runtime_claims_required"]
        if claim_states.get(claim) != "PASS"
    ]
    if missing_claims:
        return _gate(
            "FAIL",
            "Required live-host claims are not PASS.",
            missing_or_nonpass_claims=missing_claims,
            observed_claim_states=claim_states,
        )

    floor = observation["floor_sha"]
    if not isinstance(floor, str) or not re.fullmatch(r"[0-9a-f]{40}", floor):
        return _gate("FAIL", "Live-host observation floor_sha is invalid.")
    if _resolve(root, floor) is None:
        return _gate(
            "BLOCKED",
            "Live-host observation floor commit is unavailable in this checkout.",
            floor_sha=floor,
        )
    if not local_head:
        return _gate(
            "BLOCKED",
            "Local HEAD is unavailable; observation freshness cannot be checked.",
            floor_sha=floor,
        )
    ancestry = _git(root, "merge-base", "--is-ancestor", floor, local_head)
    if ancestry.returncode != 0:
        return _gate(
            "FAIL",
            "Live-host observation floor is not an ancestor of current HEAD.",
            floor_sha=floor,
            local_head=local_head,
        )

    changes_ok, changes = _projection_changes(
        root, base=floor, head=local_head, paths=paths
    )
    if not changes_ok:
        return _gate(
            "BLOCKED",
            "Unable to compare projection surfaces against the live observation floor.",
            floor_sha=floor,
        )
    changed = sorted(
        set(
            changes["committed"]
            + changes["staged"]
            + changes["unstaged"]
            + changes["untracked"]
        )
    )
    if changed:
        return _gate(
            "FAIL",
            "Agent projection changed after the live-host observation.",
            floor_sha=floor,
            local_head=local_head,
            changed_paths=changed,
        )

    return _gate(
        "PASS",
        "Normalized live-host observation verifies the current agent projection.",
        floor_sha=floor,
        local_head=local_head,
        required_claims=agent["runtime_claims_required"],
        observed_at=observation["observed_at"],
        host_version=observation.get("host_version"),
    )


def _remote_write_gate(
    root: Path,
    *,
    profile: dict[str, Any],
    agent_id: str,
    local_head: str | None,
    probe: bool,
) -> dict[str, Any]:
    if not probe:
        return _gate("NOT_RUN", "Remote-write dry-run probe was not requested.")
    if not local_head:
        return _gate("BLOCKED", "Local HEAD is unavailable for remote-write probe.")

    remote = profile["repository"]["remote"]
    namespace = profile["remote_write"]["dry_run_namespace"].rstrip("/")
    target_ref = f"{namespace}/{agent_id}/{local_head[:12]}"
    proc = _git(root, "push", "--dry-run", remote, f"{local_head}:{target_ref}")
    if proc.returncode != 0:
        return _gate(
            "FAIL",
            "Git push dry-run failed.",
            remote=remote,
            target_ref=target_ref,
            return_code=proc.returncode,
        )
    return _gate(
        "PASS",
        "Git push dry-run proved a reachable update path without mutating a remote ref.",
        remote=remote,
        target_ref=target_ref,
        expected_sha=local_head,
        proof_ceiling="Dry-run only; no remote ref mutation is proven.",
    )


def _actual_push_gate(
    root: Path,
    *,
    profile: dict[str, Any],
    local_head: str | None,
    actual_push_ref: str | None,
) -> dict[str, Any]:
    if actual_push_ref is None:
        return _gate("NOT_RUN", "No explicit pushed branch ref was supplied for readback.")
    if not actual_push_ref.startswith("refs/heads/"):
        return _gate(
            "FAIL",
            "Actual push proof accepts only explicit refs/heads/* references.",
            remote_ref=actual_push_ref,
        )
    if not local_head:
        return _gate(
            "BLOCKED",
            "Local HEAD is unavailable for actual push readback.",
            remote_ref=actual_push_ref,
        )

    remote = profile["repository"]["remote"]
    proc = _git(root, "ls-remote", "--heads", remote, actual_push_ref)
    if proc.returncode != 0:
        return _gate(
            "FAIL",
            "Remote readback failed.",
            remote=remote,
            remote_ref=actual_push_ref,
            return_code=proc.returncode,
        )
    rows = [line.split("\t", 1) for line in proc.stdout.splitlines() if "\t" in line]
    matches = [sha for sha, ref in rows if ref == actual_push_ref]
    if not matches:
        return _gate(
            "FAIL",
            "Remote branch does not exist; no actual push is proven.",
            remote=remote,
            remote_ref=actual_push_ref,
            expected_sha=local_head,
        )
    observed = matches[0]
    if observed != local_head:
        return _gate(
            "FAIL",
            "Remote branch does not equal the expected local HEAD.",
            remote=remote,
            remote_ref=actual_push_ref,
            expected_sha=local_head,
            observed_sha=observed,
        )
    return _gate(
        "PASS",
        "Remote readback proves the explicit pushed branch equals local HEAD.",
        remote=remote,
        remote_ref=actual_push_ref,
        expected_sha=local_head,
        observed_sha=observed,
    )


def _diagnosis(
    gates: dict[str, dict[str, Any]],
    required_gates: list[str],
) -> str:
    checkout = gates["REPOSITORY_CHECKOUT_CURRENT"]["state"]
    projection = gates["AGENT_PROJECTION_MATCHES_BASELINE"]["state"]
    runtime = gates["LOCAL_AGENT_RUNTIME_VERIFIED"]["state"]
    remote_write = gates["REMOTE_WRITE_VERIFIED"]["state"]
    actual_push = gates["ACTUAL_PUSH_PROVEN"]["state"]

    if checkout == "FAIL" and projection == "FAIL":
        return "STALE_LOCAL_AGENT_PROJECTION"
    if checkout == "PASS" and projection == "FAIL":
        return "LOCAL_AGENT_PROJECTION_DRIFT"
    if checkout == "PASS" and projection == "PASS" and runtime == "FAIL":
        return "CURRENT_LOCAL_AGENT_RUNTIME_FAILURE"
    if runtime == "PASS" and remote_write == "FAIL":
        return "REMOTE_WRITE_PATH_FAILURE"
    if "ACTUAL_PUSH_PROVEN" in required_gates and remote_write == "PASS" and actual_push != "PASS":
        return "ACTUAL_PUSH_NOT_PROVEN"
    if all(gates[gate]["state"] == "PASS" for gate in required_gates):
        return "LOCAL_AGENT_READY"
    return "READINESS_INCOMPLETE"


def assess_readiness(
    repo_root: Path,
    profile: dict[str, Any],
    *,
    agent_id: str,
    refresh_remote: bool = False,
    runtime_observation: Path | None = None,
    probe_remote_write: bool = False,
    actual_push_ref: str | None = None,
) -> dict[str, Any]:
    root = repo_root.expanduser().resolve()
    if _git(root, "rev-parse", "--show-toplevel").returncode != 0:
        raise ReadinessError(f"{root} is not a Git checkout")

    agent = _agent(profile, agent_id)
    paths = projection_paths(profile, agent_id)
    profile_digest = agent_profile_digest(profile, agent_id)

    checkout, baseline, local_head, refresh = _checkout_gate(
        root, profile=profile, refresh_remote=refresh_remote
    )
    gates = {
        "REPOSITORY_CHECKOUT_CURRENT": checkout,
        "AGENT_PROJECTION_MATCHES_BASELINE": _projection_gate(
            root,
            baseline=baseline,
            local_head=local_head,
            paths=paths,
        ),
        "LOCAL_AGENT_RUNTIME_VERIFIED": _runtime_gate(
            root,
            agent_id=agent_id,
            agent=agent,
            profile_digest=profile_digest,
            observation_path=runtime_observation,
            local_head=local_head,
            paths=paths,
        ),
        "REMOTE_WRITE_VERIFIED": _remote_write_gate(
            root,
            profile=profile,
            agent_id=agent_id,
            local_head=local_head,
            probe=probe_remote_write,
        ),
        "ACTUAL_PUSH_PROVEN": _actual_push_gate(
            root,
            profile=profile,
            local_head=local_head,
            actual_push_ref=actual_push_ref,
        ),
    }

    required_gates = list(agent["required_gates"])
    ready = all(gates[gate]["state"] == "PASS" for gate in required_gates)
    return {
        "schema_version": "local-agent-readiness-receipt/v1",
        "agent_id": agent_id,
        "state": "READY" if ready else "NOT_READY",
        "diagnosis": _diagnosis(gates, required_gates),
        "required_gates": required_gates,
        "local_head": local_head,
        "remote_baseline_sha": baseline,
        "agent_profile_sha256": profile_digest,
        "remote_refresh": refresh,
        "projection_paths": paths,
        "gates": gates,
        "proof_ceiling": (
            "Receipt is exact-checkout and exact-agent-profile evidence. "
            "Repository CI alone cannot satisfy live-host or real-push gates."
        ),
    }
