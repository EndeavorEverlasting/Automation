#!/usr/bin/env python3
"""CLI for the Windows silent scheduled-task capability.

Examples::

  python capabilities/windows-silent-scheduled-task/silent_cron.py resolve-pythonw
  python .../silent_cron.py classify-fixture --fixture fixtures/schtasks-list.pythonw.fixture.txt
  python .../silent_cron.py render --registry fixtures/registry.synthetic.v1.json --job-id demo_tick
  python .../silent_cron.py ensure --registry <consumer-registry.json> --job-id <id> --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CAP_ROOT = Path(__file__).resolve().parent
if str(CAP_ROOT) not in sys.path:
    sys.path.insert(0, str(CAP_ROOT))

from core.ensure import (  # noqa: E402
    classify_schtasks_list,
    ensure_job,
    query_schtasks,
)
from core.pythonw import resolve_pythonw  # noqa: E402
from core.registry import list_jobs, load_registry  # noqa: E402
from core.silence_audit import audit_evidence  # noqa: E402


def _print(obj: object) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Windows silent scheduled-task incubation CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("resolve-pythonw", help="Print resolved pythonw.exe path")

    p_fix = sub.add_parser("classify-fixture", help="Classify a captured schtasks /FO LIST dump")
    p_fix.add_argument("--fixture", type=Path, required=True)

    p_audit = sub.add_parser("audit-evidence", help="Read-only, multi-repository silence evidence classification")
    p_audit.add_argument("--input", type=Path, required=True, help="JSON snapshot using silence-evidence/v1")

    p_pre = sub.add_parser("preflight", help="Read-only preinstall check of every scheduled SILENT_BACKGROUND job")
    p_pre.add_argument("--registry", type=Path, required=True)
    p_pre.add_argument("--repo-root", type=Path, required=True)

    p_list = sub.add_parser("list-jobs", help="List jobs from a consumer registry")
    p_list.add_argument("--registry", type=Path, required=True)

    p_render = sub.add_parser("render", help="Render PowerShell registration without applying")
    p_render.add_argument("--registry", type=Path, required=True)
    p_render.add_argument("--job-id", required=True)
    p_render.add_argument("--repo-root", type=Path, default=None)

    p_ensure = sub.add_parser("ensure", help="Render or apply silent registration for one job")
    p_ensure.add_argument("--registry", type=Path, required=True)
    p_ensure.add_argument("--job-id", required=True)
    p_ensure.add_argument("--repo-root", type=Path, default=None)
    p_ensure.add_argument(
        "--apply",
        action="store_true",
        help="Actually Register-ScheduledTask (Windows only; mutates Task Scheduler)",
    )

    p_query = sub.add_parser("query-task", help="Query one task name via schtasks (live)")
    p_query.add_argument("--task-name", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "resolve-pythonw":
        _print({"pythonw": str(resolve_pythonw())})
        return 0

    if args.cmd == "classify-fixture":
        text = args.fixture.read_text(encoding="utf-8")
        _print(classify_schtasks_list(text, present=True))
        return 0

    if args.cmd == "audit-evidence":
        try:
            snapshot = json.loads(args.input.read_text(encoding="utf-8"))
            _print(audit_evidence(snapshot))
            return 0
        except (OSError, ValueError, TypeError) as exc:
            _print({"ok": False, "error": type(exc).__name__, "reason": str(exc), "mutation": "NONE"})
            return 2

    if args.cmd == "preflight":
        try:
            jobs = list_jobs(args.registry)
            root = args.repo_root.resolve()
            checked = []
            for job in jobs:
                script = (root / job["script"]).resolve()
                if root not in script.parents or not script.is_file() or script.suffix.lower() != ".py":
                    raise ValueError(f"job {job['id']}: script must be an existing Python file inside repo-root")
                checked.append({
                    "id": job["id"], "task_name": job["task_name"],
                    "execution_class": job["execution_class"],
                    "registration_launcher": "pythonw.exe", "hidden": True,
                    "interval_min": job["interval_min"],
                })
            _print({
                "ok": True, "status": "REGISTRATION_POLICY_CONFORMANT",
                "contract": "automation.silent-background/v1",
                "mutation": "NONE", "job_count": len(checked), "jobs": checked,
                "proof_ceiling": "READ_ONLY_INSTALL_PREFLIGHT_NOT_RUNTIME_CERTIFICATION"
            })
            return 0
        except (OSError, ValueError, TypeError) as exc:
            _print({"ok": False, "status": "REJECTED_PREFLIGHT", "mutation": "NONE",
                    "error": type(exc).__name__, "reason": str(exc)})
            return 2

    if args.cmd == "list-jobs":
        load_registry(args.registry)
        _print({"jobs": list_jobs(args.registry)})
        return 0

    if args.cmd in {"render", "ensure"}:
        if args.repo_root is None:
            parser.error("--repo-root is required for render/ensure")
        repo_root = args.repo_root.resolve()
        if args.cmd == "render":
            result = ensure_job(
                args.job_id,
                registry=args.registry,
                repo_root=repo_root,
                apply=False,
            )
        else:
            if args.apply and sys.platform != "win32":
                _print({"ok": False, "error": "live ensure --apply is Windows-only"})
                return 2
            result = ensure_job(
                args.job_id,
                registry=args.registry,
                repo_root=repo_root,
                apply=bool(args.apply),
            )
        _print(result)
        return 0 if result.get("ok") else 1

    if args.cmd == "query-task":
        if sys.platform != "win32":
            _print({"ok": False, "error": "query-task is Windows-only"})
            return 2
        present, raw = query_schtasks(args.task_name)
        classified = classify_schtasks_list(raw, present=present)
        classified["task_name"] = args.task_name
        _print(classified)
        return 0 if present else 1

    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
