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
from core.protocol_fabric import load_profiles, negotiate
from core.transport import read_json_object

CAP_ROOT = Path(__file__).resolve().parent
PROTOCOL_REGISTRY = CAP_ROOT / "profiles" / "current.v1.json"
CANONICAL_EVENT = {
    "beforeSubmitPrompt": "prompt.submit",
    "stop": "session.stop",
    "sessionStart": "session.start",
}


def _write_receipt(
    receipt_dir: str | None,
    receipt: dict,
) -> tuple[str | None, str | None]:
    if not receipt_dir:
        return None, None
    try:
        root = Path(receipt_dir).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        path = root / f"cursor-hook-{receipt['event']}-{stamp}.json"
        path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return str(path), None
    except OSError as exc:
        # Receipt persistence is observational only. It must never become a
        # new hook-availability dependency.
        return None, type(exc).__name__


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

    payload, transport = read_json_object(sys.stdin.buffer)
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
    ok = transport["state"] == "PARSED" and validation["state"] == "VALID"
    protocol_route = None
    if payload is not None:
        registry = json.loads(PROTOCOL_REGISTRY.read_text(encoding="utf-8"))
        protocol_route = negotiate(
            load_profiles(registry),
            host_family="cursor",
            canonical_event=CANONICAL_EVENT[args.event],
            host_event=args.event,
            payload=payload,
            host_version=os.environ.get("CURSOR_VERSION"),
        )

    receipt = {
        "schema_version": "agent-hook-runtime-observation/v1",
        "event": args.event,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "cursor_version": os.environ.get("CURSOR_VERSION"),
        "project_dir_present": bool(os.environ.get("CURSOR_PROJECT_DIR")),
        "transport": transport,
        "event_schema": validation,
        "protocol_route": protocol_route,
        "session_identity": (
            session_identity_receipt(payload)
            if args.event == "sessionStart" and payload is not None and ok
            else (
                {"state": "NOT_ACCEPTED"}
                if args.event == "sessionStart"
                else {"state": "NOT_APPLICABLE"}
            )
        ),
        "failure_policy": args.failure_policy,
        "proof_ceiling": (
            "Observes hook transport/schema and protocol-shape negotiation only; does not "
            "prove agent-policy execution, prompt resolution, host response acceptance, or provider correctness."
        ),
    }
    receipt_path, receipt_error = _write_receipt(args.receipt_dir, receipt)

    if ok:
        response = neutral_response(args.event, payload)
    elif args.failure_policy == "allow":
        # Diagnostic mode may let a malformed event pass, but it must never
        # initialize session state from an invalid sessionStart payload.
        response = {} if args.event == "sessionStart" else neutral_response(args.event, payload)
    else:
        suffix = f" Diagnostic receipt: {receipt_path}." if receipt_path else ""
        if receipt_error:
            suffix += f" Diagnostic receipt unavailable ({receipt_error})."
        response = blocked_response(
            args.event,
            "Cursor hook transport/schema validation failed; policy execution was not attempted."
            + suffix,
        )

    print(json.dumps(response, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
