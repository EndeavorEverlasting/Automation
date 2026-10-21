"""Resolve the windowless Python launcher used by silent Windows cron."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def resolve_pythonw(*, python: str | None = None) -> Path:
    """Return ``pythonw.exe`` beside ``python`` (or from PATH).

    Console ``python.exe`` / ``py.exe`` flash Windows Terminal under Task
    Scheduler. Silent jobs must launch ``pythonw.exe`` (PE subsystem GUI).
    """
    candidate_python = python or shutil.which("python") or sys.executable
    cand = Path(candidate_python).resolve().parent / "pythonw.exe"
    if cand.is_file():
        return cand
    by_name = shutil.which("pythonw")
    if by_name:
        return Path(by_name)
    raise FileNotFoundError(
        "pythonw.exe not found beside python (required for silent Windows cron)"
    )


def task_to_run_is_silent_pythonw(task_to_run: str | None) -> bool:
    """True when Task Scheduler 'Task To Run' begins with pythonw.exe.

    Anchors on the executable, not a script path that happens to contain
    the substring ``pythonw.exe``.
    """
    import re

    if not task_to_run:
        return False
    return bool(
        re.match(
            r'^\s*(?:"[^"]*[/\\]pythonw\.exe"|[^\s"]*[/\\]pythonw\.exe|'
            r'"?pythonw\.exe"?)(?:\s|$)',
            task_to_run,
            flags=re.IGNORECASE,
        )
    )
