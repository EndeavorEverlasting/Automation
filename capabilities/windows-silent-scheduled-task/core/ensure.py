"""Render and optionally apply silent Task Scheduler registrations."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .pythonw import resolve_pythonw, task_to_run_is_silent_pythonw
from .registry import job_by_id
from .schtasks_parse import classify_status, parse_schtasks_list
from .win_subprocess import run as discreet_run


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_register_powershell(
    job: dict[str, Any],
    *,
    pythonw: Path,
    repo_root: Path,
) -> str:
    """Return PowerShell that fully registers one Hidden pythonw task.

    Full Register-ScheduledTask (not ``schtasks /Change /TR`` alone) so Hidden
    and other settings are not left stale — qbit-config failure-handling rule.
    """
    script_path = (repo_root / str(job["script"])).resolve()
    args = str(job.get("args") or "").strip()
    interval = int(job["interval_min"])
    run_level = str(job.get("run_level") or "Limited")
    task_name = str(job["task_name"])
    arg = f'"{script_path}"' + (f" {args}" if args else "")
    return f"""
$ErrorActionPreference = 'Stop'
$pythonw = {_ps_literal(str(pythonw))}
$repo = {_ps_literal(str(repo_root.resolve()))}
$task = {_ps_literal(task_name)}
$arg = {_ps_literal(arg)}
$action = New-ScheduledTaskAction -Execute $pythonw -Argument $arg -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes {interval})
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -MultipleInstances IgnoreNew -Hidden
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel {run_level}
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "OK $task"
""".strip()


def classify_task_to_run(task_to_run: str) -> dict[str, Any]:
    fields = {"Task To Run": task_to_run}
    return {
        "task_to_run": task_to_run,
        "silent_pythonw": task_to_run_is_silent_pythonw(task_to_run),
        "fields": fields,
    }


def classify_schtasks_list(text: str, *, present: bool = True) -> dict[str, Any]:
    fields = parse_schtasks_list(text) if present else {}
    task_to_run = fields.get("Task To Run", "")
    return {
        "present": present,
        "status": classify_status(fields, present=present),
        "task_to_run": task_to_run or None,
        "silent_pythonw": task_to_run_is_silent_pythonw(task_to_run),
        "next_run": fields.get("Next Run Time") or None,
        "last_run_time": fields.get("Last Run Time") or None,
        "last_run_result": fields.get("Last Result") or None,
        "fields": fields,
    }


def query_schtasks(task_name: str) -> tuple[bool, str]:
    try:
        proc = discreet_run(
            ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST", "/V"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        text = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode == 0, text.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def ensure_job(
    job_id: str,
    *,
    registry: Path,
    repo_root: Path,
    apply: bool = False,
) -> dict[str, Any]:
    """Render (and optionally apply) a silent registration for one job."""
    job = job_by_id(job_id, registry)
    pythonw = resolve_pythonw() if apply else Path("C:/Synthetic/Python/pythonw.exe")
    script_path = (repo_root / str(job["script"])).resolve()
    if repo_root.resolve() not in script_path.parents:
        raise ValueError("script must remain inside declared repository root")
    if not script_path.is_file():
        return {
            "ok": False,
            "id": job_id,
            "action": "ensure",
            "error": f"missing script {script_path}",
            "apply": apply,
        }
    ps = render_register_powershell(job, pythonw=pythonw, repo_root=repo_root)
    result: dict[str, Any] = {
        "ok": True,
        "id": job_id,
        "action": "ensure",
        "apply": apply,
        "pythonw": str(pythonw),
        "task_name": job["task_name"],
        "powershell": ps,
        "repair_mode": "render_only",
    }
    if not apply:
        return result
    try:
        proc = discreet_run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True, timeout=90, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.update(ok=False, repair_mode="register", error=type(exc).__name__,
                      proof_ceiling="live registration unverified; existing task preserved where provider allows")
        return result
    present, raw = query_schtasks(str(job["task_name"]))
    classified = classify_schtasks_list(raw, present=present)
    result.update(
        {
            "ok": proc.returncode == 0 and bool(classified.get("silent_pythonw")),
            "repair_mode": "register",
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "")[:800],
            "stderr": (proc.stderr or "")[:800],
            "after": classified,
        }
    )
    return result
