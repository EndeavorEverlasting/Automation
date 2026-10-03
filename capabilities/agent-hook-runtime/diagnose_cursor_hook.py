#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from adapters.cursor import (
    SUPPORTED_EVENTS,
    blocked_response,
    neutral_response,
    session_identity_receipt,
    validate_event,
)
from core.transport import parse_json_object


def _write_receipt(receipt_dir: str | None, receipt: dict) -> str | None:
    if not receipt_dir:
        return None
    root = Path(receipt_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = root / f"cursor-hook-{receipt['event']}-{stamp}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Privacy-safe Cursor hook transport probe")
    parser.add_argument("--event", required=True, choices=sorted(SUPPORTED_EVENTS))
    parser.add_argument(
        "--failure-policy",
        choices=("allow", "block"),
        default="allow",
        help="Whether malformed transport/schema should block the host event",
    )
    parser.add_argument(
        "--receipt-dir",
        default=os.environ.get("AUTOMATION_HOOK_RECEIPT_DIR"),
        help="Optional local directory for privacy-safe diagnostic receipts",
    )
    args = parser.parse_args(argv)

    raw = sys.stdin.buffer.read()
    payload, transport = parse_json_object(raw)
    validation = (
        validate_event(args.event, payload)
        if payload is not None
        else {
            "schema_version": "cursor-hook-schema-validation/v1",
            "event": args.event,
            "state": "NOT_VALIDATED_TRANSPORT_FAILURE",
            "errors": [],
        }
    )

    receipt = {
        "schema_version": "agent-hook-runtime-observation/v1",
        "event": args.event,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "cursor_version": os.environ.get("CURSOR_VERSION"),
        "project_dir_present": bool(os.environ.get("CURSOR_PROJECT_DIR")),
        "transport": transport,
        "event_schema": validation,
        "session_identity": (
            session_identity_receipt(payload)
            if args.event == "sessionStart" and payload is not None
            else {"state": "NOT_APPLICABLE"}
        ),
        "failure_policy": args.failure_policy,
        "proof_ceiling": (
            "Observes hook transport/schema only; does not prove agent-policy execution, "
            "prompt resolution, or provider correctness."
        ),
    }
    receipt_path = _write_receipt(args.receipt_dir, receipt)

    ok = transport["state"] == "PARSED" and validation["state"] == "VALID"
    if ok:
        response = neutral_response(args.event, payload)
    elif args.failure_policy == "allow":
        response = neutral_response(args.event, payload)
    else:
        suffix = f" Diagnostic receipt: {receipt_path}." if receipt_path else ""
        response = blocked_response(
            args.event,
            "Cursor hook transport/schema validation failed; policy execution was not attempted."
            + suffix,
        )

    print(json.dumps(response, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
