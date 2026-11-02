"""Entire-local continuous development admission and receipt classification.

Deterministic offline core. Does not invoke Entire, mutate Task Scheduler,
or require GitHub Actions. Consumers supply observed facts; this module
classifies them against the incubating Automation contract.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

CONTRACT_ID = "automation.entire-local-continuous/v1"
RECEIPT_CONTRACT_ID = "automation.entire-local-continuous.receipt/v1"
SILENCE_OWNER = "capabilities/windows-silent-scheduled-task"
FLEET_OWNER = "EndeavorEverlasting/github-config"

ADOPTION_ORDER = (
    "UNVERIFIED",
    "DETECTED",
    "READY_TO_ENABLE",
    "ENABLED_LOCAL",
    "VALIDATED_LOCAL",
    "RECOVERY_PROVEN",
    "REMOTE_POLICY_RESOLVED",
    "CHECKPOINT_SYNC_PROVEN",
    "ADOPTED",
)

BLOCKER_STATES = frozenset(
    {
        "ENTIRE_MISSING",
        "DIRTY_BLOCKED",
        "NOT_SET_UP",
        "DOCTOR_FAILED",
        "WORKFLOW_DRIFT",
        "REMOTE_PUSH_WITHOUT_POLICY",
        "ACTIONS_REQUIRED_CLAIM",
        "SILENCE_BYPASS",
        "CONSOLE_CRON_PROPOSED",
        "INTERACTIVE_SCHEDULED_CLASS",
        "UNKNOWN_STATUS",
    }
)

REQUIRED_ENABLE_FLAGS = frozenset({"--local", "--skip-push-sessions"})
FORBIDDEN_AFK_LAUNCHERS = frozenset(
    {
        "powershell.exe",
        "pwsh.exe",
        "cmd.exe",
        "wt.exe",
        "windowsTerminal.exe".lower(),
        "python.exe",
    }
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def classify_entire_status(
    status: Mapping[str, Any] | None,
    *,
    entire_installed: bool,
    doctor_ok: bool | None = None,
    workflow_invariant: bool | None = None,
    checkpoint_push_policy: str = "LOCAL_ONLY_INITIAL",
) -> dict[str, Any]:
    """Map observed Entire facts to a typed adoption/blocker state."""
    reasons: list[str] = []
    if not entire_installed:
        return {
            "contract_id": CONTRACT_ID,
            "adoption_state": "ENTIRE_MISSING",
            "enabled": False,
            "reasons": ["entire_binary_absent"],
            "proof_ceiling": "CLASSIFICATION_ONLY",
        }

    payload = _as_dict(status)
    error = str(payload.get("error") or "").strip().lower()
    enabled = bool(payload.get("enabled"))
    agents = payload.get("agents")

    if not enabled or error in {"not set up", "not_set_up"}:
        reasons.append("repository_not_enabled")
        return {
            "contract_id": CONTRACT_ID,
            "adoption_state": "DETECTED",
            "enabled": False,
            "agents": agents,
            "reasons": reasons,
            "proof_ceiling": "CLASSIFICATION_ONLY",
        }

    state = "ENABLED_LOCAL"
    if doctor_ok is True and workflow_invariant is True:
        state = "VALIDATED_LOCAL"
        reasons.append("doctor_ok")
        reasons.append("workflow_invariant")
    elif doctor_ok is False:
        state = "DOCTOR_FAILED"
        reasons.append("doctor_failed")
    elif workflow_invariant is False:
        state = "WORKFLOW_DRIFT"
        reasons.append("workflow_digest_changed")

    if checkpoint_push_policy not in {
        "LOCAL_ONLY_INITIAL",
        "LOCAL_ONLY",
        "SEPARATE_PRIVATE_CHECKPOINT_REPO",
        "SAME_PRIVATE_REPO",
        "UNDECIDED",
    }:
        reasons.append("unknown_checkpoint_push_policy")

    if checkpoint_push_policy in {"UNDECIDED", "LOCAL_ONLY_INITIAL", "LOCAL_ONLY"}:
        reasons.append("remote_checkpoint_push_not_authorized")
    elif state == "VALIDATED_LOCAL":
        # Remote policy may later promote beyond VALIDATED_LOCAL; not automatic.
        reasons.append("local_validated_remote_policy_separate_gate")

    return {
        "contract_id": CONTRACT_ID,
        "adoption_state": state,
        "enabled": True,
        "agents": agents,
        "reasons": reasons,
        "checkpoint_push_policy": checkpoint_push_policy,
        "proof_ceiling": "CLASSIFICATION_ONLY",
    }


def check_workflow_invariance(before: str | None, after: str | None) -> dict[str, Any]:
    """Prove GitHub Actions workflow tree was not mutated by Entire adoption."""
    before_norm = "ABSENT" if before in (None, "") else str(before)
    after_norm = "ABSENT" if after in (None, "") else str(after)
    ok = before_norm == after_norm
    return {
        "contract_id": CONTRACT_ID,
        "invariant": "GITHUB_ACTIONS_OPTIONAL_UNCHANGED",
        "pass": ok,
        "before": before_norm,
        "after": after_norm,
        "blocker": None if ok else "WORKFLOW_DRIFT",
        "proof_ceiling": "DIGEST_COMPARISON_ONLY",
    }


def _launcher_basename(path: str) -> str:
    name = path.replace("\\", "/").rstrip("/").split("/")[-1]
    return name.lower()


def admit_afk_continuous_loop(proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Fail-closed admission for AFK continuous development / silent cron proposals.

    Agents inventing Task Scheduler jobs, console hosts, or Actions-required
    AFK loops are rejected here before any live ensure/apply.
    """
    violations: list[str] = []
    notes: list[str] = []

    silence_owner = str(proposal.get("silence_owner") or "").strip()
    if silence_owner != SILENCE_OWNER:
        violations.append("SILENCE_BYPASS")
        notes.append(
            "scheduled silent work must name capabilities/windows-silent-scheduled-task"
        )

    execution_class = str(proposal.get("execution_class") or "").strip()
    if execution_class and execution_class != "SILENT_BACKGROUND":
        violations.append("INTERACTIVE_SCHEDULED_CLASS")
        notes.append("scheduled AFK ticks require SILENT_BACKGROUND")

    launcher = str(proposal.get("scheduled_execute") or proposal.get("launcher") or "").strip()
    proposes_schedule = bool(
        proposal.get("job_id")
        or proposal.get("task_name")
        or proposal.get("schedule_kind")
        or launcher
    )
    if proposes_schedule and not launcher:
        violations.append("CONSOLE_CRON_PROPOSED")
        notes.append("scheduled AFK proposal requires scheduled_execute=pythonw.exe")
    elif launcher:
        base = _launcher_basename(launcher)
        if "pythonw" in base:
            notes.append("pythonw launcher admitted under silence owner")
        elif base == "node.exe":
            notes.append(
                "node.exe host requires silence-owner windowsHide/CREATE_NO_WINDOW chain"
            )
        elif base in FORBIDDEN_AFK_LAUNCHERS or base.endswith(".exe"):
            violations.append("CONSOLE_CRON_PROPOSED")
            notes.append(
                f"launcher {base!r} is not admitted; require pythonw.exe via silence owner"
            )
        else:
            violations.append("CONSOLE_CRON_PROPOSED")
            notes.append(f"unrecognized launcher {base!r}")

    actions_policy = str(proposal.get("actions_policy") or "").strip()
    if actions_policy in {"REQUIRED", "BLOCKING", "GITHUB_ACTIONS_REQUIRED"}:
        violations.append("ACTIONS_REQUIRED_CLAIM")
        notes.append(
            "GitHub Actions is optional evidence; Entire + local validators own AFK continuity"
        )
    elif actions_policy and actions_policy not in {
        "OPTIONAL_UNCHANGED",
        "ABSENT_OK",
        "OPTIONAL",
    }:
        notes.append(f"unknown actions_policy {actions_policy!r}; treat as review item")

    entire_mode = str(proposal.get("entire_mode") or "").strip()
    if entire_mode and entire_mode not in {
        "LOCAL_ONLY_INITIAL",
        "LOCAL_ONLY",
        "ENABLED_LOCAL",
        "VALIDATED_LOCAL",
    }:
        if entire_mode in {"PUSH_SESSIONS", "REMOTE_CHECKPOINTS"}:
            violations.append("REMOTE_PUSH_WITHOUT_POLICY")
            notes.append("remote checkpoint push requires an explicit resolved policy gate")

    enable_flags = proposal.get("entire_enable_flags")
    if isinstance(enable_flags, Sequence) and not isinstance(enable_flags, (str, bytes)):
        flag_set = {str(f) for f in enable_flags}
        missing = REQUIRED_ENABLE_FLAGS - flag_set
        if missing:
            violations.append("REMOTE_PUSH_WITHOUT_POLICY")
            notes.append(
                "initial enable must include --local and --skip-push-sessions; missing: "
                + ",".join(sorted(missing))
            )

    fullscreen_disruption = proposal.get("may_disrupt_fullscreen")
    if fullscreen_disruption is True:
        violations.append("CONSOLE_CRON_PROPOSED")
        notes.append("AFK ticks must not disrupt fullscreen; refuse may_disrupt_fullscreen=true")

    preserves_clock = proposal.get("preserves_existing_clock")
    if preserves_clock is False:
        notes.append(
            "clock rewrite is out of band for silence admission; retain consumer cadence owners"
        )

    admitted = not violations
    return {
        "contract_id": CONTRACT_ID,
        "admitted": admitted,
        "violations": sorted(set(violations)),
        "notes": notes,
        "required_owners": {
            "silence": SILENCE_OWNER,
            "fleet_adoption_inventory": FLEET_OWNER,
            "local_semantic_proof": "repository-owned validators/tests/builds",
            "session_continuity": "Entire CLI (local-first)",
        },
        "non_owners": {
            "github_actions": "optional independent evidence only",
            "product_tick_scripts": "consumer-owned",
            "prompt_kit": "TokenCorridor upstream",
        },
        "proof_ceiling": "ADMISSION_CLASSIFICATION_NOT_LIVE_ENABLE_OR_DUE_TIME",
    }


def build_receipt(
    *,
    repository: str,
    classification: Mapping[str, Any],
    workflow: Mapping[str, Any] | None = None,
    admission: Mapping[str, Any] | None = None,
    evidence_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compose a portable continuous-local receipt (no private paths required)."""
    receipt: MutableMapping[str, Any] = {
        "schema_version": RECEIPT_CONTRACT_ID,
        "contract_id": CONTRACT_ID,
        "repository": repository,
        "entire_classification": dict(classification),
        "workflow_invariance": dict(workflow) if workflow else None,
        "afk_admission": dict(admission) if admission else None,
        "evidence_refs": list(evidence_refs or []),
        "proof_ceiling": "SUPPLIED_EVIDENCE_CLASSIFICATION",
    }
    blockers = []
    state = str(classification.get("adoption_state") or "")
    if state in BLOCKER_STATES:
        blockers.append(state)
    if workflow and not workflow.get("pass", True):
        blockers.append(str(workflow.get("blocker") or "WORKFLOW_DRIFT"))
    if admission and not admission.get("admitted", True):
        blockers.extend(list(admission.get("violations") or []))
    receipt["blockers"] = sorted(set(blockers))
    receipt["ready_for_afk_continuous"] = (
        state in {"ENABLED_LOCAL", "VALIDATED_LOCAL", "RECOVERY_PROVEN", "ADOPTED"}
        and not receipt["blockers"]
        and (admission is None or bool(admission.get("admitted")))
        and (workflow is None or bool(workflow.get("pass")))
    )
    return dict(receipt)
