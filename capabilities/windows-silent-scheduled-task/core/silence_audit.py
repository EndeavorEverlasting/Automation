"""Read-only, repository-neutral Windows scheduled-task silence evidence audit.

This module classifies *supplied evidence*, not the live workstation. Neither
Task Scheduler nor application settings are queried or modified here.
"""
from __future__ import annotations

import re
from pathlib import PureWindowsPath
from typing import Any, Mapping

INPUT_SCHEMA = "automation.windows-silent-scheduled-task.silence-evidence/v1"
OUTPUT_SCHEMA = "automation.windows-silent-scheduled-task.silence-audit/v1"
_HIDDEN_PS = re.compile(r"(?i)(?:^|\s)-(?:windowstyle|w)(?:\s+|\s*=\s*)hidden(?:\s|$)")


def _command(command: str) -> tuple[str, str]:
    """Read only the launch executable; never match pythonw in script arguments."""
    text = command.strip()
    if not text:
        return "", ""
    if text.startswith('"'):
        end = text.find('"', 1)
        if end < 0:
            return "", ""
        token, rest = text[1:end], text[end + 1 :]
        if rest and not rest[0].isspace():
            return "", ""
    else:
        token, _, rest = text.partition(" ")
    return PureWindowsPath(token).name.casefold(), rest.strip()


def _nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _read_observation(task: Mapping[str, Any]) -> tuple[bool, bool, dict[str, int], list[str]]:
    observation = task.get("due_time")
    if observation is None:
        return False, False, {}, ["DUE_TIME_NOT_OBSERVED"]
    if not isinstance(observation, dict):
        raise ValueError("due_time must be an object when supplied")
    count = _nonnegative_int(observation.get("samples"), "due_time.samples")
    hits = _nonnegative_int(observation.get("console_title_hits"), "due_time.console_title_hits")
    if hits > count:
        raise ValueError("console_title_hits cannot exceed samples")
    if "sync_process_samples" in observation:
        _nonnegative_int(observation["sync_process_samples"], "due_time.sync_process_samples")
    if any(type(observation.get(k)) is not bool for k in ("due_time_matched", "foreground_preserved")):
        raise ValueError("due_time_matched and foreground_preserved must be booleans")
    details = {"samples": count, "console_title_hits": hits}
    if "sync_process_samples" in observation:
        details["sync_process_samples"] = observation["sync_process_samples"]
    flash = bool(observation["due_time_matched"] and hits > 0)
    valid = bool(
        observation["due_time_matched"] and count > 0 and hits == 0
        and observation["foreground_preserved"]
    )
    reasons: list[str] = []
    if flash:
        reasons.append("FOREGROUND_CONSOLE_HIT")
    if not observation["due_time_matched"]:
        reasons.append("DUE_TIME_NOT_MATCHED")
    elif not count:
        reasons.append("EMPTY_DUE_TIME_SAMPLE")
    elif hits == 0 and not observation["foreground_preserved"]:
        reasons.append("FOREGROUND_NOT_PRESERVED")
    return valid, flash, details, reasons


def _functional_state(value: object) -> str:
    if value is None or type(value) is bool:
        return "UNKNOWN"
    try:
        result = int(str(value).strip())
    except ValueError:
        return "UNKNOWN"
    return "ZERO" if result == 0 else "NONZERO"


def audit_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic evidence classification, with separate silence and job-result dimensions."""
    if not isinstance(task, dict):
        raise ValueError("each task must be an object")
    for key in ("id", "task_name", "task_to_run"):
        if not isinstance(task.get(key), str) or not task[key].strip():
            raise ValueError(f"task.{key} must be a nonempty string")
    if type(task.get("hidden")) is not bool:
        raise ValueError("task.hidden must be a boolean (never inferred from command)")
    if "launcher_no_window" in task and type(task["launcher_no_window"]) is not bool:
        raise ValueError("launcher_no_window must be a boolean")
    executable, args = _command(task["task_to_run"])
    reasons: list[str] = []
    compliant = False
    if executable == "pythonw.exe":
        launcher_class = "PYTHONW"
        compliant = task["hidden"]
    elif executable in ("powershell.exe", "pwsh.exe"):
        if _HIDDEN_PS.search(args):
            launcher_class = "HIDDEN_POWERSHELL"
            compliant = task["hidden"]
        else:
            launcher_class = "CONSOLE_RISK"
            reasons.append("POWERSHELL_WITHOUT_HIDDEN_WINDOWSTYLE")
    elif executable == "node.exe" and task.get("launcher_no_window") is True:
        launcher_class = "DECLARED_WINDOWLESS_NODE"
        compliant = task["hidden"]
        reasons.append("NODE_WINDOWLESS_DECLARATION_REQUIRES_RUNTIME_PROOF")
    elif executable in ("python.exe", "py.exe", "cmd.exe", "node.exe", "conhost.exe"):
        launcher_class = "CONSOLE_RISK"
        reasons.append("CONSOLE_SUBSYSTEM_LAUNCHER")
    else:
        launcher_class = "UNKNOWN"
        reasons.append("UNRECOGNIZED_LAUNCHER")
    if not task["hidden"]:
        reasons.append("TASK_HIDDEN_FALSE")
    due_valid, flash, observation, due_reasons = _read_observation(task)
    reasons.extend(due_reasons)
    cert = task.get("certification") or {}
    if not isinstance(cert, dict):
        raise ValueError("certification must be an object")
    child = cert.get("child_processes") == "CERTIFIED"
    focus = cert.get("focus") == "CERTIFIED" and cert.get("focus_mode") == "fullscreen"
    proof = isinstance(cert.get("proof_ref"), str) and bool(cert["proof_ref"].strip())
    if not child:
        reasons.append("CHILD_PROCESS_CERTIFICATION_MISSING")
    if not focus:
        reasons.append("FULLSCREEN_FOCUS_CERTIFICATION_MISSING")
    if not proof:
        reasons.append("CERTIFICATION_RECEIPT_MISSING")
    qualified = bool(compliant and due_valid and child and focus and proof and not flash)
    if flash:
        state = "FLASH_OBSERVED"
    elif qualified:
        state = "SILENT_CERTIFIED"
    elif due_valid and compliant:
        state = "DUE_TIME_OBSERVED"
    elif compliant:
        state = "LAUNCHER_COMPLIANT"
    else:
        state = "REVIEW"
    # Hidden PowerShell remains on the review queue until independently certified;
    # a single zero-flash observation is not enough.
    review = bool(not qualified and (not compliant or launcher_class == "HIDDEN_POWERSHELL" or flash))
    if launcher_class == "DECLARED_WINDOWLESS_NODE" and not qualified:
        review = True
    return {
        "id": task["id"],
        "task_name": task["task_name"],
        "launcher_class": launcher_class,
        "launcher_compliant": compliant,
        "silence_state": state,
        "silence_review": review,
        "functional_state": _functional_state(task.get("last_result")),
        "due_time_sample": observation,
        "reason_codes": sorted(set(reasons)),
        "certification_proof_ref": cert.get("proof_ref") if proof else None,
    }


def audit_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != INPUT_SCHEMA:
        raise ValueError(f"expected schema {INPUT_SCHEMA}")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks must be a nonempty array")
    results = [audit_task(task) for task in tasks]
    if len({r["id"] for r in results}) != len(results):
        raise ValueError("task ids must be unique")
    if len({r["task_name"].casefold() for r in results}) != len(results):
        raise ValueError("task names must be unique case-insensitively")
    return {
        "schema": OUTPUT_SCHEMA,
        "proof_ceiling": "SUPPLIED_EVIDENCE_CLASSIFICATION_NOT_LIVE_PROVIDER_VALIDATION",
        "mutation": "NONE",
        "summary": {
            "task_count": len(results),
            "launcher_compliant_count": sum(1 for r in results if r["launcher_compliant"]),
            "silence_review_count": sum(1 for r in results if r["silence_review"]),
            "due_time_observed_count": sum(1 for r in results if r["silence_state"] in ("DUE_TIME_OBSERVED", "SILENT_CERTIFIED")),
            "silent_certified_count": sum(1 for r in results if r["silence_state"] == "SILENT_CERTIFIED"),
            "functional_nonzero_count": sum(1 for r in results if r["functional_state"] == "NONZERO"),
        },
        "tasks": results,
    }
