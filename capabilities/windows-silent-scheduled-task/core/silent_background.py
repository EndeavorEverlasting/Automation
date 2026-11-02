"""Opt-in SILENT_BACKGROUND Windows child-process policy.

The clock (Task Scheduler, AFK, app timer) and business function stay with the
consumer. This guard only owns launch policy, no-console flags and private receipts.
It cannot certify grandchildren that bypass the wrapper or GUI side effects.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Sequence

CONTRACT = "automation.silent-background/v1"
EXECUTION_CLASSES = frozenset({"SILENT_BACKGROUND", "INTERACTIVE"})
SAFE_CONSOLE = frozenset({
    "python.exe", "pythonw.exe", "python", "python3",
    "node.exe", "node", "git.exe", "git", "rg.exe", "rg",
    "schtasks.exe", "schtasks", "tasklist.exe", "tasklist",
    "pwsh.exe", "pwsh", "powershell.exe", "powershell",
})
INTERACTIVE = frozenset({
    "explorer.exe", "explorer", "msiexec.exe", "msiexec",
    "winget.exe", "winget", "chrome.exe", "chrome", "msedge.exe",
    "firefox.exe", "rundll32.exe", "runas.exe", "runas",
    "cmd.exe", "cmd", "wscript.exe", "cscript.exe",
})
INTERACTIVE_POWERSHELL = frozenset({
    "read-host", "get-credential", "start-process", "-verb", "runas",
})
_JOB_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


def _exe(value: str) -> str:
    return PureWindowsPath(value.strip('"')).name.casefold()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "Automation" / "SilentBackground" / "receipts"
    return Path.home() / ".local" / "state" / "automation" / "silent-background"


def _persist(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".silent-",
            suffix=".tmp", delete=False,
        ) as stream:
            tmp = stream.name
            json.dump(data, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def _decision(argv: Sequence[str], *, approved_tools: frozenset[str]) -> str | None:
    if not isinstance(argv, (list, tuple)) or not argv:
        return "INVALID_ARGV"
    if any(not isinstance(s, str) or not s.strip() for s in argv):
        return "INVALID_ARGV"
    exe = _exe(argv[0])
    if exe in INTERACTIVE or exe.endswith((".bat", ".cmd", ".ps1")):
        return "INTERACTIVE_OR_SHELL_LAUNCHER"
    if exe not in SAFE_CONSOLE and exe not in approved_tools:
        return "EXECUTABLE_NOT_ADMITTED"
    if exe in {"pwsh.exe", "pwsh", "powershell.exe", "powershell"}:
        flags = {s.casefold() for s in argv[1:]}
        if not ({"-noninteractive", "-noni"} & flags):
            return "POWERSHELL_REQUIRES_NONINTERACTIVE"
        if not ({"-noprofile", "-nop"} & flags):
            return "POWERSHELL_REQUIRES_NOPROFILE"
        # Syntax is intentionally conservative: defer scripts that explicitly
        # request a UI, privilege elevation, or in-process child launch.
        tokens = re.findall(r"[a-z][a-z0-9-]*", " ".join(argv[1:]).casefold())
        if any(token in {"read-host", "get-credential", "start-process", "runas", "verb"} for token in tokens):
            return "POWERSHELL_INTERACTIVE_ACTION"
    return None


def _windows_options(kwargs: dict[str, Any]) -> dict[str, Any]:
    opts = dict(kwargs)
    if sys.platform == "win32":
        current = int(opts.get("creationflags") or 0)
        if current & (0x00000010 | 0x00000008):
            raise ValueError("CREATE_NEW_CONSOLE/DETACHED_PROCESS conflict with SILENT_BACKGROUND")
        opts["creationflags"] = current | getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000
        )
        # STARTF_USESHOWWINDOW / SW_HIDE is an additional launcher safeguard,
        # not proof against child GUI windows.
        info = opts.get("startupinfo") or subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = subprocess.SW_HIDE
        opts["startupinfo"] = info
    return opts


class SilentBackground:
    """One opt-in policy boundary for unattended launches and private receipts."""

    def __init__(self, *, job_id: str, receipt_dir: Path | None = None,
                 approved_tools: Sequence[str] = ()) -> None:
        if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
            raise ValueError("job_id must be a safe, stable identifier")
        self.job_id = job_id
        self.receipt_dir = Path(receipt_dir) if receipt_dir is not None else _receipt_dir()
        self.approved_tools = frozenset(_exe(x) for x in approved_tools)

    def execute(self, argv: Sequence[str], *, execution_class: str = "SILENT_BACKGROUND",
                timeout: float = 60, wait: bool = True, **kwargs: Any) -> dict[str, Any]:
        """Run or spawn a child without a foreground console when scheduled.

        Interactive work must be *intentionally* requested, and must never be
        invoked by a scheduled tick. No shell=True; no raw command string.
        """
        if execution_class not in EXECUTION_CLASSES:
            raise ValueError("unknown execution class")
        if type(wait) is not bool:
            raise ValueError("wait must be boolean")
        if kwargs.get("shell") not in (None, False):
            raise ValueError("shell=True is forbidden by this API")
        if "stdin" in kwargs or "stdout" in kwargs or "stderr" in kwargs:
            raise ValueError("std streams are managed by the silence boundary")
        if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(x, str) or not x.strip() for x in argv):
            raise ValueError("argv must be a nonempty argument list")
        if "capture_output" in kwargs or "check" in kwargs or "timeout" in kwargs:
            raise ValueError("capture_output, check and timeout are controlled by this API")
        if wait and (type(timeout) not in (int, float) or timeout <= 0):
            raise ValueError("timeout must be positive")
        reason = (_decision(argv, approved_tools=self.approved_tools)
                  if execution_class == "SILENT_BACKGROUND" else None)
        command_id = hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()[:16]
        packet: dict[str, Any] = {
            "schema": CONTRACT,
            "job_id": self.job_id, "timestamp_utc": _utc_now(),
            "execution_class": execution_class,
            "command_digest": command_id,
            "executable": _exe(argv[0]) if argv else None,
            "status": "DEFERRED_INTERACTION" if reason else "PENDING",
            "reason_code": reason,
            "mutated_scheduler": False,
            "proof_ceiling": "LAUNCH_POLICY_ONLY_NOT_DESCENDANT_OR_FULLSCREEN_CERTIFIED",
        }
        target = self.receipt_dir / f"{self.job_id}.receipt.json"
        if reason:
            _persist(target, packet)
            packet["receipt_path"] = str(target)
            return packet
        # No unattended execution may begin without a writable private receipt.
        # Intentional interactive launches preserve their existing UI/IO and
        # are not made dependent on Automation's unattended receipt store.
        if execution_class == "SILENT_BACKGROUND":
            _persist(target, packet)
        opts = dict(kwargs)
        opts["shell"] = False
        if execution_class == "SILENT_BACKGROUND":
            opts["stdin"] = subprocess.DEVNULL
            opts = _windows_options(opts)
        try:
            if wait:
                if execution_class == "SILENT_BACKGROUND":
                    proc = subprocess.run(list(argv), capture_output=True, timeout=timeout,
                                          check=False, **opts)
                    packet.update(stdout_bytes=len(proc.stdout or b""),
                                  stderr_bytes=len(proc.stderr or b""))
                else:
                    proc = subprocess.run(list(argv), timeout=timeout, check=False, **opts)
                packet.update(status="SUCCEEDED" if proc.returncode == 0 else "NONZERO",
                              returncode=proc.returncode)
            else:
                if execution_class == "SILENT_BACKGROUND":
                    opts.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc = subprocess.Popen(list(argv), **opts)
                packet.update(status="SPAWNED_NOT_CERTIFIED", pid=proc.pid)
        except subprocess.TimeoutExpired:
            packet.update(status="TIMEOUT", reason_code="CHILD_TIMEOUT")
        except OSError as exc:
            packet.update(status="LAUNCH_FAILED", reason_code=type(exc).__name__)
        finally:
            if execution_class == "SILENT_BACKGROUND":
                _persist(target, packet)
        packet["receipt_path"] = str(target) if execution_class == "SILENT_BACKGROUND" else None
        return packet
