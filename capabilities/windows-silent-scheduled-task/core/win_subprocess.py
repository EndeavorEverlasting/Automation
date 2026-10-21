"""Windows no-console subprocess helpers for scheduled / GUI-parent work.

Incubated here so consumer repositories (qbit-config, TokenCorridor, others)
can depend on one Automation-owned pattern instead of forking copies.

On Windows, console-subsystem children (git, PowerShell, winget, tasklist)
must not allocate a foreground console when the parent is ``pythonw.exe``.
Do not use this to hide UAC or interactive installer UI.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any


def _discreet(kwargs: dict[str, Any]) -> dict[str, Any]:
    if sys.platform == "win32":
        kwargs["creationflags"] = int(kwargs.get("creationflags") or 0) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000
        )
    return kwargs


def run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(*args, **_discreet(kwargs))


def popen(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
    return subprocess.Popen(*args, **_discreet(kwargs))
