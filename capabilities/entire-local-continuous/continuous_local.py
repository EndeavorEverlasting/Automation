#!/usr/bin/env python3
"""CLI for Entire-local continuous development admission (Automation incubation).

Examples:
  python capabilities/entire-local-continuous/continuous_local.py classify-status \\
    --status-json fixtures/entire-status.not-setup.v1.json --entire-installed

  python capabilities/entire-local-continuous/continuous_local.py check-workflows \\
    --before ABSENT --after ABSENT

  python capabilities/entire-local-continuous/continuous_local.py admit-afk \\
    --proposal fixtures/afk-proposal.admitted.v1.json

  python capabilities/entire-local-continuous/continuous_local.py receipt \\
    --repository EndeavorEverlasting/Example \\
    --status-json fixtures/entire-status.enabled-local.v1.json \\
    --entire-installed --doctor-ok --workflow-before DIGEST_A --workflow-after DIGEST_A \\
    --proposal fixtures/afk-proposal.admitted.v1.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.continuous_local import (
    admit_afk_continuous_loop,
    build_receipt,
    check_workflow_invariance,
    classify_entire_status,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _print(payload: dict) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    status = _load_json(Path(args.status_json)) if args.status_json else {}
    result = classify_entire_status(
        status,
        entire_installed=bool(args.entire_installed),
        doctor_ok=args.doctor_ok,
        workflow_invariant=args.workflow_invariant,
        checkpoint_push_policy=args.checkpoint_push_policy,
    )
    _print(result)
    return 0 if result["adoption_state"] not in {
        "ENTIRE_MISSING",
        "DOCTOR_FAILED",
        "WORKFLOW_DRIFT",
        "UNKNOWN_STATUS",
    } else 2


def cmd_workflows(args: argparse.Namespace) -> int:
    result = check_workflow_invariance(args.before, args.after)
    _print(result)
    return 0 if result["pass"] else 2


def cmd_admit(args: argparse.Namespace) -> int:
    proposal = _load_json(Path(args.proposal))
    result = admit_afk_continuous_loop(proposal)
    _print(result)
    return 0 if result["admitted"] else 2


def cmd_receipt(args: argparse.Namespace) -> int:
    status = _load_json(Path(args.status_json)) if args.status_json else {}
    classification = classify_entire_status(
        status,
        entire_installed=bool(args.entire_installed),
        doctor_ok=args.doctor_ok,
        workflow_invariant=(
            None
            if args.workflow_before is None or args.workflow_after is None
            else args.workflow_before == args.workflow_after
        ),
        checkpoint_push_policy=args.checkpoint_push_policy,
    )
    workflow = None
    if args.workflow_before is not None or args.workflow_after is not None:
        workflow = check_workflow_invariance(args.workflow_before, args.workflow_after)
    admission = None
    if args.proposal:
        admission = admit_afk_continuous_loop(_load_json(Path(args.proposal)))
    receipt = build_receipt(
        repository=args.repository,
        classification=classification,
        workflow=workflow,
        admission=admission,
        evidence_refs=args.evidence_ref or [],
    )
    _print(receipt)
    return 0 if receipt.get("ready_for_afk_continuous") else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Entire-local continuous development admission (Automation)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_cls = sub.add_parser("classify-status", help="Classify entire status --json facts")
    p_cls.add_argument("--status-json", required=True)
    p_cls.add_argument("--entire-installed", action="store_true")
    p_cls.add_argument("--doctor-ok", action=argparse.BooleanOptionalAction, default=None)
    p_cls.add_argument(
        "--workflow-invariant", action=argparse.BooleanOptionalAction, default=None
    )
    p_cls.add_argument("--checkpoint-push-policy", default="LOCAL_ONLY_INITIAL")
    p_cls.set_defaults(func=cmd_classify)

    p_wf = sub.add_parser("check-workflows", help="Compare workflow digests")
    p_wf.add_argument("--before", required=True)
    p_wf.add_argument("--after", required=True)
    p_wf.set_defaults(func=cmd_workflows)

    p_ad = sub.add_parser("admit-afk", help="Admit or reject an AFK continuous proposal")
    p_ad.add_argument("--proposal", required=True)
    p_ad.set_defaults(func=cmd_admit)

    p_rc = sub.add_parser("receipt", help="Build a continuous-local receipt")
    p_rc.add_argument("--repository", required=True)
    p_rc.add_argument("--status-json", required=True)
    p_rc.add_argument("--entire-installed", action="store_true")
    p_rc.add_argument("--doctor-ok", action=argparse.BooleanOptionalAction, default=None)
    p_rc.add_argument("--workflow-before", default=None)
    p_rc.add_argument("--workflow-after", default=None)
    p_rc.add_argument("--checkpoint-push-policy", default="LOCAL_ONLY_INITIAL")
    p_rc.add_argument("--proposal", default=None)
    p_rc.add_argument("--evidence-ref", action="append", default=[])
    p_rc.set_defaults(func=cmd_receipt)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Allow `python continuous_local.py` from this directory or repo root.
    cap_dir = Path(__file__).resolve().parent
    if str(cap_dir) not in sys.path:
        sys.path.insert(0, str(cap_dir))
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
